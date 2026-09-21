// Uses the same Chat path as the app, without SwiftUI, IPC or per-token printing.
#include "mimir/chat.h"
#include "model.h"
#include "nlohmann/json.hpp"
#include <chrono>
#include <fstream>
#include <iostream>

using Clock = std::chrono::steady_clock;
using json = nlohmann::ordered_json;
static double seconds(Clock::time_point a, Clock::time_point b) {
    return std::chrono::duration<double>(b - a).count();
}
int main(int argc, char ** argv) {
    try {
        if (argc != 3) { throw std::runtime_error("usage: mimir-native-bench MODEL PROFILE_JSON"); }
        json profile; std::ifstream(argv[2]) >> profile;
        llama_log_set([](ggml_log_level level, const char * text, void *) {
            if (level == GGML_LOG_LEVEL_ERROR) { std::cerr << text; }
        }, nullptr);
        ggml_backend_load_all(); llama_backend_init();
        const auto loadStart = Clock::now();
        auto model = mimir::tools::load_model(argv[1], "metal");
        mimir::Config config;
        config.context_tokens = config.batch_tokens = 8192;
        config.allow_context_extension = true;
        config.flash_attention = true;
        config.threads = profile.at("threads");
        const std::string system = profile.at("systemPrompt");
        mimir::Chat chat(model, config, system);
        mimir::TextCodec codec(model);
        std::cout << json{{"event", "setup"}, {"load_seconds", seconds(loadStart, Clock::now())},
            {"context", 8192}, {"batch", 8192}, {"threads", config.threads}, {"reply_budget", 64},
            {"flash_attention", true}, {"kv", "F16"}, {"sampling", "greedy"}}.dump() << std::endl;
        const std::string request = "Skriv en sammenhængende historie på mindst 500 ord om en rejse til Odense. Begynd historien med det samme.";
        std::string longPrompt = "Baggrundsnoter til historien:\n";
        for (int i = 0; i < 32; ++i) {
            longPrompt += "Rejsen foregår med tog. Familien vil besøge et museum, gå langs åen og spise vegetarisk frokost. De har en hel weekend og vil gerne opleve byens historie.\n";
        }
        longPrompt += request;
        const std::string prompts[] = {request, longPrompt};
        for (int round = 0; round < 4; ++round) {
            for (int slot = 0; slot < 2; ++slot) {
                const int index = round % 2 ? 1 - slot : slot;
                chat.reset();
                const auto prefix = codec.prepare({{"system", system}, {"user", prompts[index]}});
                std::string firstChunk;
                auto first = Clock::time_point{}, last = Clock::time_point{};
                const auto start = Clock::now();
                const auto reply = chat.reply(prompts[index], 64, [&](const std::string & text) {
                    last = Clock::now();
                    if (firstChunk.empty()) { first = last; firstChunk = text; }
                });
                const auto end = Clock::now();
                if (reply.status != mimir::Status::ok || firstChunk.empty()) { throw std::runtime_error("generation failed"); }
                // UTF-8 streaming can group several tokens in the first visible chunk.
                size_t firstTokens = 0;
                std::string firstBytes;
                while (firstTokens < reply.tokens.size() && firstBytes.size() < firstChunk.size()) {
                    firstBytes += codec.piece(reply.tokens[firstTokens++]);
                }
                if (firstBytes != firstChunk || last <= first) { throw std::runtime_error("cannot measure stream interval"); }
                std::cout << json{{"event", "sample"}, {"warmup", round == 0}, {"round", round},
                    {"case", index ? "long" : "short"}, {"prompt_tokens", prefix.tokens.size()},
                    {"output_tokens", reply.tokens.size()}, {"first_chunk_tokens", firstTokens},
                    {"first_chunk", firstChunk}, {"ttft_seconds", seconds(start, first)},
                    {"decode_tokens_per_second", (reply.tokens.size() - firstTokens) / seconds(first, last)},
                    {"total_seconds", seconds(start, end)}, {"finish", int(reply.finish)},
                    {"output", reply.text}}.dump() << std::endl;
            }
        }
    } catch (const std::exception & e) { std::cerr << e.what() << '\n'; return 1; }
}
