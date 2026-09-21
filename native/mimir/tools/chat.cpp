#include "mimir/chat.h"
#include "model.h"
#include "nlohmann/json.hpp"
#include <chrono>
#include <csignal>
#include <iostream>
#include <limits>
#include <thread>

using json = nlohmann::ordered_json;
namespace {
std::atomic<bool> interrupted{false};
static_assert(std::atomic<bool>::is_always_lock_free, "signal handling requires lock-free atomics");
void on_interrupt(int) { interrupted.store(true, std::memory_order_relaxed); }

class CancelWatch {
public:
    explicit CancelWatch(mimir::Chat & chat) : worker_([this, &chat] {
        while (!stop_.load(std::memory_order_relaxed)) {
            if (interrupted.exchange(false, std::memory_order_relaxed)) { chat.request_cancel(); }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
    }) {}
    ~CancelWatch() { stop_.store(true); worker_.join(); }
private:
    std::atomic<bool> stop_{false};
    std::thread worker_;
};

uint32_t positive(int64_t value) {
    if (value <= 0 || value > INT32_MAX) { throw std::invalid_argument("limits must be positive 32-bit integers"); }
    return uint32_t(value);
}

uint32_t parse_limit(const std::string & value) {
    size_t consumed = 0;
    const auto result = std::stoll(value, &consumed);
    if (consumed != value.size()) { throw std::invalid_argument("invalid numeric limit: " + value); }
    return positive(result);
}

const char * finish_name(mimir::Finish finish) {
    switch (finish) {
        case mimir::Finish::eos: return "eos";
        case mimir::Finish::length: return "length";
        case mimir::Finish::cancelled: return "cancelled";
        default: return "error";
    }
}

void event(const json & value) { std::cout << value.dump() << std::endl; }

void quiet_log(ggml_log_level level, const char * text, void *) {
    if (level == GGML_LOG_LEVEL_ERROR) { std::cerr << text; }
}
}

int main(int argc, char ** argv) {
    try {
        std::string model_path, device = "auto", system;
        mimir::Config config;
        uint32_t max_tokens = 256;
        bool json_mode = false, inspect = false, verbose = false, list_devices = false;
        for (int i = 1; i < argc; ++i) {
            std::string arg = argv[i];
            if (arg == "--list-devices") { list_devices = true; continue; }
            if (arg == "--json") { json_mode = true; continue; }
            if (arg == "--inspect") { inspect = true; continue; }
            if (arg == "--verbose") { verbose = true; continue; }
            if (arg == "--flash") { config.flash_attention = true; continue; }
            if (arg == "--help") {
                std::cout << "mimir-chat --model MODEL [--device auto|cpu|BACKEND|DEVICE] [--ctx 2048] [--batch 1024]\n"
                             "           [--max-tokens 256] [--system TEXT] [--flash] [--json] [--inspect] [--verbose]\n"
                             "           --list-devices lists compiled/available backends without a model.\n"
                             "Greedy text chat. /reset starts a new conversation; /quit exits; Ctrl-C cancels generation.\n"
                             "--json reads one request per line and emits start/delta/done/error events.\n"
                             "--inspect loads vocabulary only; supports tokenize/prepare/reset, not generation.\n";
                return 0;
            }
            if (i + 1 == argc) { throw std::invalid_argument("missing value for " + arg); }
            const std::string value = argv[++i];
            if (arg == "--model") { model_path = value; }
            else if (arg == "--device") { device = value; }
            else if (arg == "--system") { system = value; }
            else if (arg == "--ctx") { config.context_tokens = parse_limit(value); }
            else if (arg == "--batch") { config.batch_tokens = parse_limit(value); }
            else if (arg == "--max-tokens") { max_tokens = parse_limit(value); }
            else { throw std::invalid_argument("unknown option: " + arg); }
        }
        if (model_path.empty() && !list_devices) { throw std::invalid_argument("--model is required; use --help"); }
        if (inspect && !json_mode) { throw std::invalid_argument("--inspect requires --json"); }
        if (!verbose) { llama_log_set(quiet_log, nullptr); ggml_log_set(quiet_log, nullptr); }
        ggml_backend_load_all();
        llama_backend_init();
        if (list_devices) {
            for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
                auto dev = ggml_backend_dev_get(i);
                event({{"device", ggml_backend_dev_name(dev)}, {"description", ggml_backend_dev_description(dev)},
                    {"backend", ggml_backend_reg_name(ggml_backend_dev_backend_reg(dev))}});
            }
            return 0;
        }
        const auto model = mimir::tools::load_model(model_path, device, inspect);
        mimir::TextCodec codec(model);
        std::unique_ptr<mimir::Chat> chat;
        if (!inspect) { chat = std::make_unique<mimir::Chat>(model, config, system); }
        std::signal(SIGINT, on_interrupt);
        if (json_mode) { event({{"event", "ready"}}); }
        else { std::cerr << "Mimir chat. /reset, /quit; Ctrl-C stops generation.\n"; }
        std::string line;
        while (true) {
            if (!json_mode) { std::cout << "You: " << std::flush; }
            if (!std::getline(std::cin, line)) { break; }
            try {
                json request = json_mode ? json::parse(line) : json{{"op", "reply"}, {"text", line}};
                std::string op = request.value("op", "reply");
                if (!json_mode && line == "/quit") { break; }
                if (!json_mode && line == "/reset") { op = "reset"; }
                if (op == "tokenize") {
                    const auto tokens = codec.tokenize(request.at("text"), request.value("add_special", false));
                    event({{"event", "tokens"}, {"tokens", tokens}, {"decoded", codec.decode(tokens)}});
                } else if (op == "prepare") {
                    std::vector<mimir::Message> messages;
                    for (const auto & m : request.at("messages")) { messages.push_back({m.at("role"), m.at("content")}); }
                    const auto prompt = codec.prepare(messages, request.value("add_generation_prompt", true));
                    event({{"event", "prompt"}, {"text", prompt.text}, {"tokens", prompt.tokens}});
                } else if (op == "reset") {
                    if (chat) { chat->reset(); }
                    if (json_mode) { event({{"event", "reset"}}); }
                } else if (op == "reply") {
                    if (!chat) { throw std::invalid_argument("generation unavailable in --inspect mode"); }
                    const std::string text = request.at("text");
                    const auto limit = positive(request.value("max_tokens", int64_t(max_tokens)));
                    interrupted.store(false);
                    if (json_mode) { event({{"event", "start"}}); }
                    else { std::cout << "Mimir: " << std::flush; }
                    mimir::Reply reply;
                    {
                        CancelWatch watch(*chat);
                        reply = chat->reply(text, limit, [&](const std::string & chunk) {
                            if (json_mode) { event({{"event", "delta"}, {"text", chunk}}); }
                            else { std::cout << chunk << std::flush; }
                        });
                    }
                    if (json_mode) {
                        event({{"event", "done"}, {"finish", finish_name(reply.finish)}, {"status", int(reply.status)},
                               {"text", reply.text}, {"tokens", reply.tokens}, {"stop_token", reply.stop_token},
                               {"history_size", chat->history().size()}});
                    } else {
                        std::cout << '\n';
                        if (reply.finish == mimir::Finish::cancelled) { std::cerr << "Cancelled; partial turn discarded.\n"; }
                        else if (reply.status == mimir::Status::capacity) { std::cerr << "Conversation exceeds context/batch or answer budget. Use /reset or larger startup limits.\n"; }
                        else if (reply.status != mimir::Status::ok) { std::cerr << "Generation failed (status " << int(reply.status) << ").\n"; }
                    }
                    if (reply.status != mimir::Status::ok) { chat->recover(); }
                } else { throw std::invalid_argument("unknown operation: " + op); }
            } catch (const std::exception & error) {
                if (chat) { chat->recover(); }
                if (json_mode) { event({{"event", "error"}, {"message", error.what()}}); }
                else { std::cerr << error.what() << '\n'; }
            }
        }
        return 0;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
