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
#include "loading.h"
#include "backend_loader.h"
using Json = nlohmann::json;
namespace {
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
            auto loaded=mimir::runtime::load(c);
            model=std::move(loaded.model);codec=std::move(loaded.codec);
            system=c.at("profile").at("systemPrompt");context=loaded.context;
            mixed_lm=c.value("mixedLM",false);conversation.clear();
            {std::lock_guard<std::mutex> lock(mutex);chat=std::move(loaded.chat);}
            emit({{"type","loaded"},{"context",context},{"trainingContext",llama_model_n_ctx_train(model.get())},
                {"device",loaded.device.id},{"backend",loaded.device.backend},
                {"fallbackReasons",loaded.failures},{"flashAttention",loaded.flash}});return;
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
            try{static std::once_flag once;std::call_once(once,[]{mimir::runtime::initialize_backends();});execute(c);}catch(const std::exception & e){if(chat) chat->recover();emit({{"type","error"},{"message",e.what()}});}
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
