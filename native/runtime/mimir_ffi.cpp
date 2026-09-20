#include "mimir_ffi.h"
#include "mimir/chat.h"
#include "model.h"
#include "mimir/compaction.h"
#include "nlohmann/json.hpp"
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <thread>
#if defined(__linux__)
#include <fstream>
#include <sstream>
#endif
#if defined(__APPLE__)
#include <mach/mach.h>
#include <TargetConditionals.h>
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
#include <os/proc.h>
#endif
#else
#include <limits>
#endif
using Json = nlohmann::json;
namespace {
uint64_t available_memory() {
#if defined(__APPLE__)
#if TARGET_OS_IOS && !TARGET_OS_SIMULATOR
    return os_proc_available_memory();
#else
    vm_statistics64_data_t stats{}; mach_msg_type_number_t n = HOST_VM_INFO64_COUNT;
    mach_port_t host = mach_host_self(); vm_size_t page = 0; host_page_size(host, &page);
    auto status = host_statistics64(host, HOST_VM_INFO64, reinterpret_cast<host_info64_t>(&stats), &n);
    mach_port_deallocate(mach_task_self(), host);
    return status == KERN_SUCCESS ? (uint64_t(stats.free_count) + stats.inactive_count) * page : 1024ull*1024*1024;
#endif
#elif defined(__linux__)
    // MemAvailable includes reclaimable cache, unlike MemFree. This also covers
    // Android; it is a sizing hint, not a guarantee against memory pressure.
    std::ifstream info("/proc/meminfo");
    std::string line;
    while (std::getline(info, line)) {
        std::istringstream fields(line);
        std::string key, unit;
        uint64_t value;
        if (fields >> key >> value >> unit && key == "MemAvailable:" && unit == "kB") {
            return value * 1024;
        }
    }
    return 1024ull*1024*1024;
#else
    // Conservative until a platform-specific available-memory probe is qualified.
    return 1024ull*1024*1024;
#endif
}
std::vector<mimir::Message> history(const Json & command) {
    std::vector<mimir::Message> out;
    for (const auto & m : command.value("history", Json::array())) out.push_back({m.at("role"),m.at("content")});
    return out;
}
mimir::compaction::Memory memory(const Json & command) {
    auto m=command.value("memory",Json::object());
    return m.is_null() ? mimir::compaction::Memory{} : mimir::compaction::Memory{m.value("summary", ""),m.value("covered",size_t(0))};
}
struct Engine {
    std::mutex mutex; std::condition_variable wake;
    std::deque<std::string> events; std::deque<Json> commands;
    std::atomic<bool> busy{false}, cancelled{false}; bool closing=false;
    std::shared_ptr<mimir::Chat> chat;
    std::shared_ptr<llama_model> model;
    std::unique_ptr<mimir::TextCodec> codec;
    std::string system, conversation; int context=0;
    bool mixed_lm=false;
    std::thread worker;
    Engine() : worker([this]{run();}) {}
    void emit(Json event) { std::lock_guard<std::mutex> lock(mutex); events.push_back(event.dump()); }
    void cancel() {
        cancelled=true;
        std::lock_guard<std::mutex> lock(mutex);
        if(chat) chat->request_cancel();
    }
    ~Engine() {
        cancel(); {std::lock_guard<std::mutex> lock(mutex);closing=true;}
        wake.notify_one();worker.join();
    }
    void execute(const Json & c) {
        const auto op=c.at("op").get<std::string>();
        if(op=="devices") {
            Json devices=Json::array();
            devices.push_back({{"id","cpu"},{"name","CPU"},{"backend","CPU"}});
            for(size_t i=0;i<ggml_backend_dev_count();++i) {
                auto d=ggml_backend_dev_get(i);
                if(ggml_backend_dev_type(d)==GGML_BACKEND_DEVICE_TYPE_CPU) continue;
                devices.push_back({{"id",ggml_backend_dev_name(d)}, {"name",ggml_backend_dev_description(d)},
                    {"backend",ggml_backend_reg_name(ggml_backend_dev_backend_reg(d))}});
            }
            emit({{"type","devices"},{"devices",devices}});return;
        }
        if(op=="load") {
            {std::lock_guard<std::mutex> lock(mutex); chat.reset();} codec.reset();model.reset();
            auto profile=c.at("profile");const auto path=c.at("path").get<std::string>();
            auto device=c.value("device", "auto");auto selected=mimir::tools::select_device(device);
            bool gpu=selected && (ggml_backend_dev_type(selected)==GGML_BACKEND_DEVICE_TYPE_GPU ||
                ggml_backend_dev_type(selected)==GGML_BACKEND_DEVICE_TYPE_IGPU);
            const int minimum=profile.at("minimumContext"),maximum=profile.at("maximumContext");
            context=c.value("context",0);
            if(!context) {
                context=minimum;const auto available=available_memory()*profile.at("memoryFraction").get<double>();
                for(int tier:profile.at("contextTiers")) {
                    long double required=c.at("modelBytes").get<uint64_t>()+profile.at("fixedMemoryBytes").get<uint64_t>()+
                        (long double)tier*profile.at("memoryBytesPerToken").get<uint64_t>()+
                        (gpu?0:(long double)tier*tier*profile.at("cpuAttentionBytesPerTokenSquared").get<uint64_t>());
                    if(required<=available) context=tier;
                }
            }
            if(context<minimum || context>maximum) throw std::runtime_error("Context is outside the model profile limits.");
            model=mimir::tools::load_model(path,device);
            char architecture[64]{};llama_model_meta_val_str(model.get(),"general.architecture",architecture,sizeof architecture);
            if(std::string(architecture)!="hrm_text" || !llama_model_is_prefix_lm(model.get())) throw std::runtime_error("Choose a PrefixLM HRMText Mimir GGUF.");
            system=profile.at("systemPrompt");
            mimir::Config config;config.context_tokens=config.batch_tokens=context;
            mixed_lm=c.value("mixedLM",false);config.mixed_lm=mixed_lm;conversation.clear();
            config.threads=profile.at("threads");config.allow_context_extension=true;
            config.flash_attention=c.value("flash",gpu);
            auto next=std::make_shared<mimir::Chat>(model,config,system);
            codec=std::make_unique<mimir::TextCodec>(model);
            {std::lock_guard<std::mutex> lock(mutex);chat=next;}
            emit({{"type","loaded"},{"context",context},{"trainingContext",llama_model_n_ctx_train(model.get())},
                {"device",selected?ggml_backend_dev_name(selected):"CPU"}});return;
        }
        if(!chat || !codec) throw std::runtime_error("Load a model first.");
        auto full=history(c);
        mimir::Chat::validate_history(full);
        auto previous=memory(c);bool compact=c.value("compact",true);
        if(op=="count") {
            auto effective=compact?mimir::compaction::remembered(full,previous):full;
            if(!system.empty()) effective.insert(effective.begin(),{"system",system});
            emit({{"type","count"},{"tokens",effective.empty()?0:codec->prepare(effective,false).tokens.size()}});return;
        }
        if(op!="reply") throw std::runtime_error("Unknown native operation.");
        const auto current=c.value("conversation",std::string{});
        if(!mixed_lm || chat->cancelled() || current!=conversation) chat->recover();
        conversation=current;
        const std::string prompt=c.at("prompt");const int budget=c.at("budget");
        if(budget<1 || budget>=context) throw std::runtime_error("Invalid reply budget.");
        auto prepared=compact?mimir::compaction::compact(*chat,*codec,system,full,previous,prompt,context,budget,
            [&]{return cancelled.load();},[&]{emit({{"type","compacting"}});},
            [&](const mimir::compaction::Memory & m){emit({{"type","summary"},{"text",m.summary},{"covered",m.covered}});})
            :mimir::compaction::PreparedHistory{full,previous,false};
        chat->restore_history(prepared.messages,mixed_lm);
        auto input=prepared.messages;if(!system.empty()) input.insert(input.begin(),{"system",system});input.push_back({"user",prompt});
        emit({{"type","prepared"},{"tokens",codec->prepare(input).tokens.size()}});
        if(cancelled || prepared.cancelled) chat->request_cancel();
        auto result=chat->reply(prompt,budget,[&](const std::string & t){emit({{"type","token"},{"text",t}});});
        const bool stopped=cancelled || result.finish==mimir::Finish::cancelled;
        if(result.status!=mimir::Status::ok && !stopped) throw std::runtime_error(result.status==mimir::Status::capacity?
            "Conversation and reply exceed context. Increase context, reduce reply budget or enable compaction.":"Native generation failed.");
        emit({{"type","reply"},{"text",result.text},{"cancelled",stopped},{"limited",result.finish==mimir::Finish::length},
            {"reusedPrefixTokens",result.reused_tokens},
            {"memory",!stopped && prepared.memory.covered?Json{{"summary",prepared.memory.summary},{"covered",prepared.memory.covered}}:Json(nullptr)}});
        if(!mixed_lm || stopped) chat->recover();
    }
    void run() {
        for(;;) {
            Json c;{std::unique_lock<std::mutex> lock(mutex);wake.wait(lock,[&]{return closing||!commands.empty();});
                if(closing) break;c=std::move(commands.front());commands.pop_front();}
            try{static std::once_flag once;std::call_once(once,[]{ggml_backend_load_all();llama_backend_init();});execute(c);}catch(const std::exception & e){if(chat) chat->recover();emit({{"type","error"},{"message",e.what()}});}
            // Clear busy before publishing completion, so the consumer can submit its next operation.
            busy=false;emit({{"type","done"}});
        }
        {std::lock_guard<std::mutex> lock(mutex);chat.reset();}codec.reset();model.reset();
    }
};
}
extern "C" {
void * mimir_create() {try {return new Engine;}catch(...){return nullptr;}}
int mimir_submit(void * p,const char * command) {
    try {auto c=Json::parse(command);auto e=static_cast<Engine*>(p);if(e->busy.exchange(true))return 0;
        {std::lock_guard<std::mutex> lock(e->mutex);e->cancelled=false;e->commands.push_back(std::move(c));}e->wake.notify_one();return 1;
    }catch(...){return -1;}
}
char * mimir_poll(void * p) {auto e=static_cast<Engine*>(p);std::lock_guard<std::mutex> lock(e->mutex);
    if(e->events.empty())return nullptr;auto s=std::move(e->events.front());e->events.pop_front();
    auto out=static_cast<char*>(std::malloc(s.size()+1));if(out)std::memcpy(out,s.c_str(),s.size()+1);return out;}
void mimir_free(char * p){std::free(p);}
void mimir_cancel(void * p){static_cast<Engine*>(p)->cancel();}
void mimir_destroy(void * p){delete static_cast<Engine*>(p);}
}
