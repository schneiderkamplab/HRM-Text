#include "mimir/chat.h"
#include "../utf8.h"
#include "../tools/model.h"
#include "jinja/parser.h"
#include "jinja/runtime.h"
#include "json.h"
#include <iostream>
#include <limits>
#include <stdexcept>

static int checks = 0;
static void require(bool condition, const char * name) {
    if (!condition) { throw std::runtime_error(name); }
    ++checks;
}

static void utf8() {
    const std::string valid = "Hello æøå 🧑🏽‍💻 中文 cafe\xcc\x81\n";
    for (size_t split = 0; split <= valid.size(); ++split) {
        mimir::detail::Utf8Stream stream;
        auto first = stream.push(valid.substr(0, split));
        mimir::detail::require_utf8(first);
        auto second = stream.push(valid.substr(split), true);
        mimir::detail::require_utf8(second);
        require(first + second == valid, "UTF-8 split stream");
    }
    for (const std::string bad : {"\xc0\xaf", "\xed\xa0\x80", "\xf4\x90\x80\x80", "\xe2\x82"}) {
        bool rejected = false;
        try { mimir::detail::require_utf8(bad); } catch (const std::invalid_argument &) { rejected = true; }
        require(rejected, "invalid UTF-8 input rejected");
        mimir::detail::Utf8Stream stream;
        auto repaired = stream.push(bad, true);
        mimir::detail::require_utf8(repaired);
        require(!repaired.empty(), "invalid UTF-8 repaired for output");
    }
    for (const auto & test : std::vector<std::pair<std::string, std::string>>{
        {"{{ '\u00a0Danmark\u2003' | trim }}", "Danmark"},
        {"{{ 'øÆhelloÆø'.strip('øÆ') }}", "hello"},
        {"{{ 'Æhelloø'.lstrip('Æ') }}", "helloø"},
        {"{{ 'Æhelloø'.rstrip('ø') }}", "Æhello"},
        {"{{ 'æhello'.strip('ø') }}", "æhello"}}) {
        jinja::lexer lexer;
        auto ast = jinja::parse_from_tokens(lexer.tokenize(test.first));
        jinja::context ctx(test.first);
        jinja::runtime runtime(ctx);
        require(runtime.gather_string_parts(runtime.execute(ast))->as_string().str() == test.second, "Unicode Jinja strip");
    }
}

int main(int argc, char ** argv) {
    try {
        utf8();
        if (argc == 3) {
            ggml_backend_load_all();
            llama_backend_init();
            auto model = mimir::tools::load_model(argv[1], argv[2]);
            mimir::TextCodec codec(model);
            codec.set_tools(R"([{"type":"function","function":{"name":"web_search","description":"Search the web","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Query"}},"required":["query"]}}}])");
            const auto declaration = codec.prepare({{"user", "Search"}}).text;
            require(declaration.find("<|tool>declaration:web_search") != std::string::npos, "OpenAI tool schema uses model template");
            const std::string transcript = R"([{"role":"assistant","content":"","tool_calls":[{"id":"s0","type":"function","function":{"name":"web_search","arguments":{"query":"test"}}}]},{"role":"tool","name":"web_search","tool_call_id":"s0","content":"A source result"}])";
            const auto continuation = codec.prepare({{"user", "Search"}, {"assistant", "", transcript}}).text;
            require(continuation.find("<|tool_call>call:web_search{query:") != std::string::npos, "native tool call rendered");
            require(continuation.find("<|tool_response>response:web_search") != std::string::npos, "OpenAI role tool rendered");
            require(continuation.size() >= 16 && continuation.substr(continuation.size()-16) == "<tool_response|>", "continue within assistant turn after tool result");
            codec.set_tools("");
            require(codec.is_end(106) && !codec.is_end(1), "only the configured checkpoint EOS terminates generation");
            mimir::Config config{256, 224, 4, true, GGML_TYPE_F16};
            mimir::Chat chat(model, config);
            const std::string prompt = "Forklar forskellen mellem vejr og klima kort.";
            std::string streamed;
            auto reference = chat.reply(prompt, 4, [&](const auto & text) { streamed += text; });
            require(reference.status == mimir::Status::ok && !reference.tokens.empty(), "real generation");
            require(streamed == reference.text && chat.history().size() == 2, "stream/history agreement");
            const auto completed = chat.history();
            auto continued = chat.reply("Uddyb kort.", 4);
            require(continued.status == mimir::Status::ok, "continued generation");
            chat.restore_history(completed);
            require(chat.reply("Uddyb kort.", 4).tokens == continued.tokens, "restored transcript continuation matches");
            const auto before_invalid = chat.history().size();
            for (const auto & invalid : std::vector<std::vector<mimir::Message>>{
                    {{"user", "unfinished"}}, {{"assistant", "wrong role"}, {"user", "bad order"}},
                    {{"user", "\xc0\xaf"}, {"assistant", "bad UTF-8"}}}) {
                bool rejected = false;
                try { chat.restore_history(invalid); } catch (const std::invalid_argument &) { rejected = true; }
                require(rejected && chat.history().size() == before_invalid, "invalid restore preserves history");
            }
            chat.reset();
            auto cancelled = chat.reply(prompt, 4, [&](const auto &) { chat.request_cancel(); });
            require(cancelled.finish == mimir::Finish::cancelled && chat.history().empty(), "callback cancellation rollback");
            require(chat.reply(prompt, 4).finish == mimir::Finish::cancelled, "sticky chat cancellation");
            chat.recover();
            require(chat.reply(prompt, 4).tokens == reference.tokens, "cancel recovery matches fresh");
            chat.reset();
            bool caught = false;
            try { chat.reply(prompt, 4, [](const auto &) { throw std::runtime_error("consumer failed"); }); }
            catch (const std::runtime_error &) { caught = true; }
            require(caught && chat.history().empty(), "callback exception rollback");
            require(chat.reply(prompt, 4).tokens == reference.tokens, "exception recovery matches fresh");
            auto saved_size = chat.history().size();
            require(chat.reply("too much", 256).status == mimir::Status::capacity && chat.history().size() == saved_size,
                    "capacity preserves completed conversation");
            require(chat.reply(prompt, 0).status == mimir::Status::invalid_input && chat.history().size() == saved_size,
                    "invalid budget preserves history");
            chat.reset();
            mimir::Sampling sampled{0.7f, 1.0f, 42, 1.2f};
            const auto sampled_reply = chat.reply(prompt, 8, {}, sampled);
            require(sampled_reply.status == mimir::Status::ok, "temperature and repetition penalty generation");
            chat.reset();
            require(chat.reply(prompt, 8, {}, sampled).tokens == sampled_reply.tokens,
                    "seeded sampling and penalty history reset between replies");
            for (float penalty : {0.9f, 2.1f, std::numeric_limits<float>::quiet_NaN()}) {
                const auto before = chat.history().size();
                bool rejected = false;
                sampled.repeat_penalty = penalty;
                try { chat.reply(prompt, 4, {}, sampled); }
                catch (const std::invalid_argument &) { rejected = true; }
                require(rejected && chat.history().size() == before, "invalid penalty preserves history");
            }
            mimir::Chat with_system(model, config, "Svar på dansk.");
            with_system.reset();
            require(with_system.history().size() == 1 && with_system.history()[0].role == "system", "reset keeps system");
        }
        std::cout << checks << " text checks passed\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
