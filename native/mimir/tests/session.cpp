#include "mimir/session.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>

using json = nlohmann::ordered_json;
using mimir::Config;
using mimir::Result;
using mimir::Session;
using mimir::Status;
namespace fs = std::filesystem;

namespace mimir {
struct SessionTestPeer {
    static void decoder(Session & session, int32_t (*decode)(llama_context *, llama_batch)) {
        session.decode_ = decode;
    }
    static bool empty(const Session & session) {
        return llama_memory_seq_pos_max(llama_get_memory(session.context_.get()), 0) == -1;
    }
};
}

static json checks = json::array();
static double tolerance;
static Session * interrupted_session;
static int injected_code;

static void require(bool passed, const std::string & name) {
    checks.push_back({{"name", name}, {"pass", passed}});
    if (!passed) {
        throw std::runtime_error("FAIL: " + name);
    }
}

static void close(const std::vector<float> & actual, const std::vector<float> & expected, const std::string & name) {
    double error = 0;
    bool valid = !actual.empty() && actual.size() == expected.size();
    if (valid) {
        for (size_t i = 0; i < actual.size(); ++i) {
            valid &= std::isfinite(actual[i]) && std::isfinite(expected[i]);
            error = std::max(error, std::abs(double(actual[i]) - expected[i]));
        }
    }
    checks.push_back({{"name", name}, {"max_abs", error}, {"pass", valid && error <= tolerance}});
    if (!valid || error > tolerance) {
        throw std::runtime_error("FAIL: " + name + " error=" + std::to_string(error));
    }
}

static std::vector<float> read_logits(const fs::path & path) {
    std::ifstream input(path, std::ios::binary | std::ios::ate);
    if (!input || input.tellg() <= 0 || input.tellg() % sizeof(float)) {
        throw std::runtime_error("invalid reference " + path.string());
    }
    std::vector<float> result(size_t(input.tellg()) / sizeof(float));
    input.seekg(0);
    input.read(reinterpret_cast<char *>(result.data()), result.size() * sizeof(float));
    if (!input) {
        throw std::runtime_error("cannot read reference");
    }
    return result;
}

static int32_t decode_test_batch(llama_context * ctx, llama_batch batch) {
    return llama_get_attention_type(ctx) == LLAMA_ATTENTION_TYPE_PREFIX_LM && batch.pos && batch.pos[0] == 0 ?
        llama_decode_prefix(ctx, batch) : llama_decode(ctx, batch);
}

static int32_t fail_after_write(llama_context * ctx, llama_batch batch) {
    const auto code = decode_test_batch(ctx, batch);
    llama_synchronize(ctx);
    if (code != 0) {
        throw std::runtime_error("fault setup decode failed");
    }
    return injected_code;
}

static int32_t cancel_after_write(llama_context * ctx, llama_batch batch) {
    const auto code = decode_test_batch(ctx, batch);
    llama_synchronize(ctx);
    std::thread canceller([] { interrupted_session->request_cancel(); });
    canceller.join();
    return code;
}

static int32_t cancel_before_compute(llama_context * ctx, llama_batch batch) {
    std::thread canceller([] { interrupted_session->request_cancel(); });
    canceller.join();
    return decode_test_batch(ctx, batch);
}

static int32_t throw_after_write(llama_context * ctx, llama_batch batch) {
    if (decode_test_batch(ctx, batch) != 0) {
        throw std::runtime_error("exception setup failed");
    }
    llama_synchronize(ctx);
    throw std::bad_alloc();
}

static void parity(std::shared_ptr<llama_model> model, const fs::path & fixture, Config config) {
    std::ifstream input(fixture / "cases.json");
    const auto cases = json::parse(input);
    if (!llama_model_is_prefix_lm(model.get())) {
        Session session(model, config);
        auto got = session.begin_turn({2, 11, 23, 37, 41, 53}, 3, true);
        require(bool(got), "causal metadata prefill");
        close(got.logits, read_logits(fixture / "oracle/causal_control-0.f32"), "causal metadata HF parity");
        return;
    }
    for (const auto & test : cases) {
        const std::string id = test.at("id");
        // These are low-level API controls, outside the session's single-sequence contract.
        if (id == "causal_control" || id == "isolated_sequence") {
            continue;
        }
        auto cfg = config;
        cfg.context_tokens = test.value("n_ctx", config.context_tokens);
        cfg.batch_tokens = test.value("n_ubatch", config.batch_tokens);
        Session session(model, cfg);
        int index = 0;
        for (const auto & step : test.at("steps")) {
            const auto tokens = step.at("tokens").get<std::vector<llama_token>>();
            const auto before = session.position();
            const bool prefix = step.at("attention") == "prefix";
            const bool all = step.value("all_logits", true);
            auto got = prefix ? session.begin_turn(tokens, cfg.context_tokens - uint32_t(tokens.size()), all)
                              : session.append(tokens, all);
            if (step.value("expect_reject", false)) {
                require(got.status == Status::capacity && session.position() == before,
                        id + " rejection preserves session");
            } else {
                require(bool(got), id + " decode " + std::to_string(index));
                close(got.logits, read_logits(fixture / "oracle" / (id + "-" + std::to_string(index) + ".f32")),
                      id + " HF parity " + std::to_string(index));
            }
            ++index;
        }
    }
}

static void lifecycle(std::shared_ptr<llama_model> model, Config cfg, bool cpu) {
    const std::vector<llama_token> prompt{2, 11, 23, 37, 41, 53};
    const std::vector<llama_token> answer{61, 73, 89};
    const int vocab = llama_vocab_n_tokens(llama_model_get_vocab(model.get()));
    cfg.context_tokens = 128;
    cfg.batch_tokens = 127;
    Session session(model, cfg);
    Session fresh(model, cfg);
    require(session.append(answer).status == Status::not_ready, "append requires a turn");
    const auto reference = fresh.begin_turn(prompt, 3);
    const auto suffix = fresh.append(answer, true);
    require(bool(reference) && bool(suffix), "fresh reference");
    require(bool(session.begin_turn(prompt, 3)), "initial turn");
    const auto rejected = [&](Result got, Status expected, const std::string & label) {
        require(got.status == expected && got.logits.empty() && session.position() == prompt.size() &&
                session.remaining() == 3 && session.ready(), label);
    };
    rejected(session.begin_turn({}, 3), Status::invalid_input, "empty prompt preserves previous turn");
    rejected(session.begin_turn({-1}, 3), Status::invalid_input, "negative token rejected");
    rejected(session.begin_turn({vocab}, 3), Status::invalid_input, "token upper bound rejected");
    rejected(session.begin_turn(prompt, 0), Status::invalid_input, "zero answer budget rejected");
    rejected(session.begin_turn(prompt, UINT32_MAX), Status::capacity, "budget overflow rejected");
    rejected(session.begin_turn(std::vector<llama_token>(128, 2), 1), Status::capacity, "oversized prefix rejected");
    rejected(session.append({}), Status::invalid_input, "empty answer rejected");
    rejected(session.append({vocab}), Status::invalid_input, "invalid answer token rejected");
    rejected(session.append({2, 3, 4, 5}), Status::capacity, "answer budget enforced");
    close(session.append(answer, true).logits, suffix.logits, "rejections preserve usable KV");
    require(session.remaining() == 0 && session.append({2}).status == Status::capacity, "exhausted budget");
    std::vector<llama_token> conversation = prompt;
    for (int turn = 0; turn < 8; ++turn) {
        conversation.insert(conversation.end(), answer.begin(), answer.end());
        conversation.push_back(11 + turn);
        close(session.begin_turn(conversation, 3).logits, fresh.begin_turn(conversation, 3).logits,
              "new turn re-prefill " + std::to_string(turn));
        close(session.append(answer).logits, fresh.append(answer).logits,
              "new turn answer " + std::to_string(turn));
    }
    // Truncation must be represented as a fresh, fully supplied prompt.
    close(session.begin_turn(prompt, 3).logits, reference.logits, "shorter retained history re-prefill");
    session.request_cancel();
    require(session.append(answer).status == Status::cancelled && !session.ready() &&
            mimir::SessionTestPeer::empty(session), "cancel between decode calls clears KV");
    require(session.begin_turn(prompt, 3).status == Status::cancelled, "cancel is sticky");
    session.reset();
    close(session.begin_turn(prompt, 3).logits, reference.logits, "reset after cancel recovers");
    for (const int code : {1, 2, -1, -3}) {
        for (bool prefix : {false, true}) {
            session.reset();
            require(bool(session.begin_turn(prompt, 3)), "failure setup");
            injected_code = code;
            mimir::SessionTestPeer::decoder(session, fail_after_write);
            auto got = prefix ? session.begin_turn(prompt, 3) : session.append(answer);
            mimir::SessionTestPeer::decoder(session, nullptr);
            require(got.status == (code == 2 ? Status::cancelled : Status::backend_error) &&
                    got.backend_code == code && got.logits.empty() && !session.ready() &&
                    session.position() == 0 && session.remaining() == 0 && mimir::SessionTestPeer::empty(session),
                    "partial backend failure cleared " + std::to_string(code) + (prefix ? " prefix" : " answer"));
            require(session.append(answer).status == (code == 2 ? Status::cancelled : Status::not_ready),
                    "failed state cannot continue");
            if (code == 2) {
                session.reset();
            }
            close(session.begin_turn(prompt, 3).logits, reference.logits, "backend failure fresh-turn recovery");
            close(session.append(answer, true).logits, suffix.logits, "backend failure causal recovery");
        }
    }
    interrupted_session = &session;
    for (const bool prefix : {false, true}) {
        session.reset();
        require(bool(session.begin_turn(prompt, 3)), "exception setup");
        mimir::SessionTestPeer::decoder(session, throw_after_write);
        bool caught = false;
        try {
            if (prefix) {
                session.begin_turn(prompt, 3);
            } else {
                session.append(answer);
            }
        } catch (const std::bad_alloc &) {
            caught = true;
        }
        mimir::SessionTestPeer::decoder(session, nullptr);
        require(caught && !session.ready() && mimir::SessionTestPeer::empty(session),
                "exception after KV write clears session");
        close(session.begin_turn(prompt, 3).logits, reference.logits, "exception recovery");
    }
    for (const bool prefix : {false, true}) {
        session.reset();
        require(bool(session.begin_turn(prompt, 3)), "cancel setup");
        mimir::SessionTestPeer::decoder(session, cancel_after_write);
        auto got = prefix ? session.begin_turn(prompt, 3) : session.append(answer);
        mimir::SessionTestPeer::decoder(session, nullptr);
        require(got.status == Status::cancelled && got.logits.empty() && mimir::SessionTestPeer::empty(session),
                "cross-thread late cancel discards completed decode");
        session.reset();
        close(session.begin_turn(prompt, 3).logits, reference.logits, "late cancel recovery");
    }
    if (cpu) {
        session.reset();
        mimir::SessionTestPeer::decoder(session, cancel_before_compute);
        auto got = session.begin_turn(std::vector<llama_token>(127, 2), 1);
        mimir::SessionTestPeer::decoder(session, nullptr);
        require(got.status == Status::cancelled && got.backend_code == 2 && mimir::SessionTestPeer::empty(session),
                "real CPU abort callback");
        session.reset();
        close(session.begin_turn(prompt, 3).logits, reference.logits, "CPU abort recovery");
    }
    session.reset();
    require(!session.ready() && session.position() == 0 && mimir::SessionTestPeer::empty(session), "explicit reset");
    require(bool(session.begin_turn(std::vector<llama_token>(127, 2), 1)), "prefix at physical capacity");
    require(bool(session.append({3})) && session.position() == 128, "fill exact context boundary");
    require(session.append({4}).status == Status::capacity && session.position() == 128, "no context shifting");
    // Owned outputs survive subsequent decode/reset; no borrowed backend pointers escape.
    session.reset();
    auto owned = session.begin_turn(prompt, 3);
    auto copy = owned.logits;
    session.append(answer);
    session.reset();
    close(owned.logits, copy, "output lifetime");
    for (const auto bad : {Config{0, 1, 4}, Config{128, 0, 4}, Config{128, 129, 4}, Config{128, 64, 0},
                           Config{UINT32_MAX, 1, 4}}) {
        bool rejected_config = false;
        try { Session invalid(model, bad); } catch (const std::invalid_argument &) { rejected_config = true; }
        require(rejected_config, "configuration rejected before allocation");
    }
}

static void full_context(std::shared_ptr<llama_model> model, Config cfg) {
    cfg.context_tokens = 4096;
    cfg.batch_tokens = 4095;
    Session session(model, cfg);
    std::vector<llama_token> prompt(4095);
    for (size_t i = 0; i < prompt.size(); ++i) {
        prompt[i] = 2 + i % 101;
    }
    const auto start = std::chrono::steady_clock::now();
    auto result = session.begin_turn(prompt, 1);
    const auto seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();
    require(bool(result) && session.position() == 4095, "real 4095-token prefix");
    checks.back()["prefill_seconds"] = seconds;
    require(bool(session.append({61})) && session.position() == 4096, "real 4096-token context boundary");
    require(session.append({73}).status == Status::capacity, "real context overflow rejected");
    require(session.begin_turn(prompt, 2).status == Status::capacity && session.position() == 4096,
            "real context reservation rejected without mutation");
    require(bool(session.begin_turn({2, 11, 23}, 1)) && session.position() == 3,
            "real full-context session starts shorter new turn");
}

int main(int argc, char ** argv) {
    if (argc != 6 && (argc != 7 || std::string(argv[6]) != "full-context")) {
        std::cerr << "usage: mimir-session-tests MODEL FIXTURE cpu|metal off|off-f16|on OUTPUT_DIR [full-context]\n";
        return 2;
    }
    const fs::path output = argv[5];
    fs::create_directories(output);
    bool passed = false;
    std::string error;
    try {
        const std::string device = argv[3];
        const std::string flash = argv[4];
        if ((device != "cpu" && device != "metal") || (flash != "on" && flash != "off" && flash != "off-f16")) {
            throw std::invalid_argument("invalid device or flash mode");
        }
        ggml_backend_load_all();
        llama_backend_init();
        ggml_backend_dev_t devices[] = {nullptr, nullptr};
        if (device == "metal") {
            for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
                auto dev = ggml_backend_dev_get(i);
                if (std::string(ggml_backend_reg_name(ggml_backend_dev_backend_reg(dev))) == "MTL") {
                    devices[0] = dev;
                    break;
                }
            }
            require(devices[0] != nullptr, "Metal required; no CPU fallback");
        }
        auto params = llama_model_default_params();
        params.n_gpu_layers = device == "cpu" ? 0 : 999;
        params.devices = devices;
        std::shared_ptr<llama_model> model(llama_model_load_from_file(argv[1], params), llama_model_free);
        require(bool(model), "model load");
        const bool real = llama_vocab_n_tokens(llama_model_get_vocab(model.get())) > 128;
        tolerance = real ? 0.03 : (device == "metal" || flash != "off" ? 0.003 : 1e-4);
        Config cfg{128, 64, 4, flash == "on", flash != "off" ? GGML_TYPE_F16 : GGML_TYPE_F32};
        if (!real) {
            Config extended = cfg;
            extended.context_tokens = uint32_t(llama_model_n_ctx_train(model.get())) + 32;
            extended.batch_tokens = extended.context_tokens;
            bool rejected = false;
            try { Session guarded(model, extended); }
            catch (const std::invalid_argument &) { rejected = true; }
            require(rejected, "training context guard remains default");
            extended.allow_context_extension = true;
            Session permitted(model, extended);
            std::vector<llama_token> longer(extended.context_tokens - 4, 1);
            require(bool(permitted.begin_turn(longer, 4)), "opt-in prefix beyond training context");
            require(bool(permitted.append({1})), "opt-in decode beyond training context");
        }
        parity(model, argv[2], cfg);
        lifecycle(model, cfg, device == "cpu");
        if (argc == 7) {
            full_context(model, cfg);
        }
        passed = true;
    } catch (const std::exception & exception) {
        error = exception.what();
        std::cerr << error << '\n';
    }
    json report{{"model", argv[1]}, {"fixture", argv[2]}, {"device", argv[3]}, {"flash", argv[4]},
                {"tolerance", tolerance}, {"checks", checks}, {"pass", passed}, {"error", error}};
    std::ofstream stream(output / "result.json");
    stream << report.dump(2) << '\n';
    std::cout << checks.size() << " checks; pass=" << passed << '\n';
    return passed && stream ? 0 : 1;
}
