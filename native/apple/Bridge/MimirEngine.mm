#import "MimirEngine.h"
#include "mimir/chat.h"
#include "model.h"
#include <atomic>
#include <algorithm>
#include <mutex>
#include <TargetConditionals.h>
#include <mach/mach.h>
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
#include <os/proc.h>
#endif

namespace {
uint64_t available_memory() {
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
    return os_proc_available_memory();
#else
    vm_statistics64_data_t stats = {};
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    mach_port_t host = mach_host_self();
    vm_size_t page = 0;
    const auto result = host_statistics64(host, HOST_VM_INFO64,
        reinterpret_cast<host_info64_t>(&stats), &count);
    host_page_size(host, &page);
    mach_port_deallocate(mach_task_self(), host);
    if (result != KERN_SUCCESS) { return NSProcessInfo.processInfo.physicalMemory / 4; }
    return std::min<uint64_t>(NSProcessInfo.processInfo.physicalMemory,
        (uint64_t(stats.free_count) + stats.inactive_count) * page);
#endif
}
// Conservative DFM-Mimir estimate: weights + headroom + recurrent KV/linear scratch.
// At 8192, Metal measured ~6 GiB KV + 8 GiB graph + 272 MiB host scratch.
// CPU attention also materializes a quadratic attention workspace.
long double required_memory(int context, uint64_t modelBytes, bool gpu) {
    const long double tokens = context;
    return modelBytes + 256.L * 1024 * 1024 + tokens * 2 * 1024 * 1024 +
        (gpu ? 0 : 96.L * tokens * tokens);
}

std::string cpp_text(NSString * value) {
    return {value.UTF8String, [value lengthOfBytesUsingEncoding:NSUTF8StringEncoding]};
}
NSString * error_text(const std::exception & error) {
    return [NSString stringWithUTF8String:error.what()] ?: @"Unable to run the model.";
}
NSString * status_text(mimir::Status status) {
    switch (status) {
        case mimir::Status::capacity: return @"This conversation and reply budget exceed the context. Increase context in settings, reduce the reply budget, or start a new chat.";
        case mimir::Status::invalid_input: return @"The message could not be processed.";
        default: return @"The model could not finish this reply. Please try again.";
    }
}
}

@implementation MimirEngine {
    dispatch_queue_t _worker;
    std::shared_ptr<mimir::Chat> _chat;
    std::mutex _lock;
    std::atomic<bool> _cancelled;
}
+ (int)recommendedContextWithUseGPU:(BOOL)useGPU modelBytes:(uint64_t)modelBytes {
    const long double budget = available_memory() * 0.70L;
    for (int context : {8192, 4096, 2048}) {
        if (required_memory(context, modelBytes, useGPU) <= budget) { return context; }
    }
    return 1024;
}
- (instancetype)init {
    if ((self = [super init])) {
        _worker = dispatch_queue_create("dk.sdu.mimir.inference", DISPATCH_QUEUE_SERIAL);
        _cancelled.store(false);
        static std::once_flag once;
        std::call_once(once, [] { ggml_backend_load_all(); llama_backend_init(); });
    }
    return self;
}
- (void)loadModel:(NSString *)path context:(int)context useGPU:(BOOL)useGPU
      completion:(void (^)(NSString *, int))completion {
    dispatch_async(_worker, ^{
        NSString * error = nil;
        int loadedContext = 0;
        @autoreleasepool {
            try {
                // Release the previous model before loading another to bound peak memory.
                { std::lock_guard<std::mutex> guard(self->_lock); self->_chat.reset(); }
                NSDictionary * attributes = [NSFileManager.defaultManager attributesOfItemAtPath:path error:nil];
                const uint64_t modelBytes = [attributes[NSFileSize] unsignedLongLongValue];
                const int resolvedContext = context == 0
                    ? [MimirEngine recommendedContextWithUseGPU:useGPU modelBytes:modelBytes] : context;
                if (resolvedContext < 1024) { throw std::runtime_error("Context must be at least 1,024 tokens."); }
                if (required_memory(resolvedContext, modelBytes, useGPU) > available_memory() * 0.70L) {
                    throw std::runtime_error("Not enough available memory for this context and model. Choose a smaller context or model, or close other apps.");
                }
                auto model = mimir::tools::load_model(path.UTF8String, useGPU ? "metal" : "cpu");
                char architecture[64] = {};
                llama_model_meta_val_str(model.get(), "general.architecture", architecture, sizeof(architecture));
                if (std::string(architecture) != "hrm_text" || !llama_model_is_prefix_lm(model.get())) {
                    throw std::runtime_error("Choose a Mimir HRMText GGUF model.");
                }
                mimir::Config config;
                config.context_tokens = config.batch_tokens = resolvedContext;
                config.threads = 4;
                config.allow_context_extension = true;
                config.flash_attention = useGPU;
                auto chat = std::make_shared<mimir::Chat>(model, config,
                    "You are Mimir, a local assistant powered by DFM-Mimir from Danish Foundation Models. "
                    "Your model was developed by Danish Foundation Models, not OpenAI. "
                    "You run on the user's device. Answer in the user's language.");
                { std::lock_guard<std::mutex> guard(self->_lock); self->_chat = std::move(chat); }
                loadedContext = resolvedContext;
            } catch (const std::exception & failure) { error = error_text(failure); }
        }
        dispatch_async(dispatch_get_main_queue(), ^{ completion(error, loadedContext); });
    });
}
- (void)reply:(NSString *)prompt history:(NSArray<NSDictionary<NSString *,NSString *> *> *)history
      budget:(int)budget onToken:(void (^)(NSString *))onToken
  completion:(void (^)(NSString *, BOOL, BOOL))completion {
    _cancelled.store(false);
    dispatch_async(_worker, ^{
        NSString * error = nil;
        BOOL cancelled = NO;
        BOOL limited = NO;
        @autoreleasepool {
            std::shared_ptr<mimir::Chat> chat;
            { std::lock_guard<std::mutex> guard(self->_lock); chat = self->_chat; }
            try {
                if (!chat) { throw std::runtime_error("Load a model first."); }
                std::vector<mimir::Message> restored;
                for (NSDictionary * entry in history) {
                    NSString * role = entry[@"role"];
                    NSString * content = entry[@"content"];
                    if (![role isKindOfClass:NSString.class] || ![content isKindOfClass:NSString.class]) {
                        throw std::runtime_error("Invalid saved conversation.");
                    }
                    restored.push_back({cpp_text(role), cpp_text(content)});
                }
                chat->restore_history(restored);
                if (self->_cancelled.load()) { chat->request_cancel(); }
                auto result = chat->reply(cpp_text(prompt), budget, [&](const std::string & text) {
                    NSString * piece = [[NSString alloc] initWithBytes:text.data() length:text.size() encoding:NSUTF8StringEncoding];
                    dispatch_async(dispatch_get_main_queue(), ^{ onToken(piece ?: @""); });
                });
                cancelled = result.finish == mimir::Finish::cancelled || self->_cancelled.load();
                limited = result.finish == mimir::Finish::length;
                if (result.status != mimir::Status::ok && !cancelled) { error = status_text(result.status); }
                chat->recover();
            } catch (const std::exception & failure) { error = error_text(failure); }
        }
        dispatch_async(dispatch_get_main_queue(), ^{ completion(error, cancelled, limited); });
    });
}
- (void)cancel {
    _cancelled.store(true);
    std::lock_guard<std::mutex> guard(_lock);
    if (_chat) { _chat->request_cancel(); }
}
@end
