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
long double required_memory(int context, uint64_t modelBytes, bool gpu, NSDictionary * profile) {
    const long double tokens = context;
    return modelBytes + [profile[@"fixedMemoryBytes"] unsignedLongLongValue] +
        tokens * [profile[@"memoryBytesPerToken"] unsignedLongLongValue] +
        (gpu ? 0 : [profile[@"cpuAttentionBytesPerTokenSquared"] unsignedLongLongValue] * tokens * tokens);
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
    BOOL _closing; // Main-thread admission; worker operations already queued are drained.
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
         profile:(NSDictionary<NSString *, id> *)profile
      completion:(void (^)(NSString *, int, int))completion {
    if (_closing) {
        dispatch_async(dispatch_get_main_queue(), ^{ completion(@"The model is shutting down.", 0, 0); });
        return;
    }
    dispatch_async(_worker, ^{
        NSString * error = nil;
        int loadedContext = 0;
        int trainingContext = 0;
        @autoreleasepool {
            try {
                // Release the previous model before loading another to bound peak memory.
                { std::lock_guard<std::mutex> guard(self->_lock); self->_chat.reset(); }
                NSDictionary * attributes = [NSFileManager.defaultManager attributesOfItemAtPath:path error:nil];
                const uint64_t modelBytes = [attributes[NSFileSize] unsignedLongLongValue];
                const int minimum = [profile[@"minimumContext"] intValue];
                const int maximum = [profile[@"maximumContext"] intValue];
                const long double fraction = [profile[@"memoryFraction"] doubleValue];
                if (minimum < 1 || maximum < minimum || fraction <= 0 || fraction > 1) {
                    throw std::runtime_error("Invalid model profile.");
                }
                int resolvedContext = context;
                if (context == 0) {
                    resolvedContext = minimum;
                    const long double budget = available_memory() * fraction;
                    for (NSNumber * tier in profile[@"contextTiers"]) {
                        const int candidate = tier.intValue;
                        if (candidate >= minimum && candidate <= maximum &&
                            required_memory(candidate, modelBytes, useGPU, profile) <= budget) {
                            resolvedContext = std::max(resolvedContext, candidate);
                        }
                    }
                    if (required_memory(resolvedContext, modelBytes, useGPU, profile) > budget) {
                        throw std::runtime_error("Not enough available memory for automatic defaults. Close other apps or choose a smaller model.");
                    }
                }
                if (resolvedContext < minimum || resolvedContext > maximum) {
                    throw std::runtime_error("Context is outside this model profile's supported range.");
                }
                // Explicit user settings bypass the estimate; real allocation remains authoritative.
                auto model = mimir::tools::load_model(path.UTF8String, useGPU ? "metal" : "cpu");
                char architecture[64] = {};
                llama_model_meta_val_str(model.get(), "general.architecture", architecture, sizeof(architecture));
                if (std::string(architecture) != "hrm_text" || !llama_model_is_prefix_lm(model.get())) {
                    throw std::runtime_error("Choose a Mimir HRMText GGUF model.");
                }
                mimir::Config config;
                config.context_tokens = config.batch_tokens = resolvedContext;
                config.threads = [profile[@"threads"] intValue];
                config.allow_context_extension = true;
                config.flash_attention = useGPU;
                auto chat = std::make_shared<mimir::Chat>(model, config, cpp_text(profile[@"systemPrompt"]));
                trainingContext = int(llama_model_n_ctx_train(model.get()));
                { std::lock_guard<std::mutex> guard(self->_lock); self->_chat = std::move(chat); }
                loadedContext = resolvedContext;
            } catch (const std::exception & failure) { error = error_text(failure); }
        }
        dispatch_async(dispatch_get_main_queue(), ^{ completion(error, loadedContext, trainingContext); });
    });
}
- (void)reply:(NSString *)prompt history:(NSArray<NSDictionary<NSString *,NSString *> *> *)history
      budget:(int)budget onToken:(void (^)(NSString *))onToken
  completion:(void (^)(NSString *, BOOL, BOOL))completion {
    if (_closing) {
        dispatch_async(dispatch_get_main_queue(), ^{ completion(@"The model is shutting down.", YES, NO); });
        return;
    }
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
- (void)shutdownWithCompletion:(void (^)(void))completion {
    _closing = YES;
    [self cancel];
    dispatch_async(_worker, ^{
        @autoreleasepool {
            std::lock_guard<std::mutex> guard(self->_lock);
            self->_chat.reset();
        }
        dispatch_async(dispatch_get_main_queue(), completion);
    });
}
- (void)cancel {
    _cancelled.store(true);
    std::lock_guard<std::mutex> guard(_lock);
    if (_chat) { _chat->request_cancel(); }
}
@end
