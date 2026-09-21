#include "mimir/chat.h"
#include "model.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <stdexcept>

int main(int argc, char ** argv) {
    try {
        if (argc != 2) { throw std::runtime_error("provide a Mimir GGUF path"); }
        ggml_backend_load_all();
        llama_backend_init();
        auto model = mimir::tools::load_model(argv[1], "metal");
        mimir::Config config{8192, 8192, 4, true, GGML_TYPE_F16};
        bool rejected = false;
        try { mimir::Session guarded(model, config); }
        catch (const std::invalid_argument &) { rejected = true; }
        if (!rejected) { throw std::runtime_error("extension must require opt-in"); }
        config.allow_context_extension = true;
        mimir::TextCodec codec(model);
        std::string text = "Læs denne tekst:";
        for (int i = 0; i < 4500; ++i) { text += " ord"; }
        text += "\nSvar med ét ord: Hvad handler teksten om?";
        const auto prompt = codec.prepare({{"user", text}});
        if (prompt.tokens.size() <= 4096 || prompt.tokens.size() + 4 > config.context_tokens) {
            throw std::runtime_error("test must cross training context within allocated context");
        }
        mimir::Session session(model, config);
        auto result = session.begin_turn(prompt.tokens, 4);
        for (int i = 0; i < 4; ++i) {
            if (!result || !std::all_of(result.logits.begin(), result.logits.end(),
                [](float value) { return std::isfinite(value); })) {
                throw std::runtime_error("extended position execution failed or nonfinite logits");
            }
            const llama_token token = std::max_element(result.logits.begin(), result.logits.end()) - result.logits.begin();
            result = session.append({token});
        }
        if (!result) { throw std::runtime_error("last extended decode failed"); }
        std::cout << "PASS: 8192 context; templated prefix " << prompt.tokens.size()
                  << " tokens; four causal decode steps beyond 4096; finite logits; default guard retained\n";
        return 0;
    } catch (const std::exception & error) { std::cerr << error.what() << '\n'; return 1; }
}
