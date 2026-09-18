#include "llama.h"
#include "ggml-backend.h"
#include "nlohmann/json.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <sys/resource.h>
#include <vector>

using json = nlohmann::ordered_json;
using clock_type = std::chrono::steady_clock;

struct causal_scope {
    llama_context * ctx;
    causal_scope(llama_context * ctx, bool causal) : ctx(ctx) {
        llama_set_causal_attn(ctx, causal);
    }
    ~causal_scope() {
        llama_synchronize(ctx);
        llama_set_causal_attn(ctx, true);
    }
};

static double elapsed_ms(clock_type::time_point start) {
    return std::chrono::duration<double, std::milli>(clock_type::now() - start).count();
}

int main(int argc, char ** argv) {
    if (argc != 7) {
        std::cerr << "usage: prefixlm-runner MODEL CASES OUTPUT_DIR baseline|existing|replacement cpu|metal off|on\n";
        return 2;
    }
    try {
        const std::string variant = argv[4];
        const std::string device = argv[5];
        if (variant != "baseline" && variant != "existing" && variant != "replacement") {
            throw std::runtime_error("invalid variant");
        }
        if (device != "cpu" && device != "metal") {
            throw std::runtime_error("invalid device");
        }
        if (std::string(argv[6]) != "on" && std::string(argv[6]) != "off") {
            throw std::runtime_error("invalid flash mode");
        }
        const bool flash = std::string(argv[6]) == "on";
        const std::filesystem::path out = argv[3];
        std::filesystem::create_directories(out);
        std::ifstream input(argv[2]);
        const json cases = json::parse(input);
        ggml_backend_load_all();
        llama_backend_init();
        auto mp = llama_model_default_params();
        mp.n_gpu_layers = device == "cpu" ? 0 : 999;
        ggml_backend_dev_t devices[] = {nullptr, nullptr};
        if (device == "metal") {
            for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
                auto candidate = ggml_backend_dev_get(i);
                auto backend = ggml_backend_dev_backend_reg(candidate);
                if (std::string(ggml_backend_reg_name(backend)) == "MTL") {
                    devices[0] = candidate;
                    break;
                }
            }
            if (!devices[0]) {
                throw std::runtime_error("Metal backend unavailable; refusing CPU fallback");
            }
        }
        mp.devices = devices;
        const auto load_start = clock_type::now();
        std::unique_ptr<llama_model, decltype(&llama_model_free)> model(
            llama_model_load_from_file(argv[1], mp), llama_model_free);
        if (!model) {
            throw std::runtime_error("model load failed");
        }
        const int n_vocab = llama_vocab_n_tokens(llama_model_get_vocab(model.get()));
#ifdef PREFIXLM_HAS_QUERY
        const bool prefix_capability = llama_model_is_prefix_lm(model.get());
#else
        const bool prefix_capability = false;
#endif
        json report = {{"variant", variant}, {"device", device}, {"flash", flash},
                       {"prefix_capability", prefix_capability},
                       {"model_load_ms", elapsed_ms(load_start)}, {"cases", json::array()}};
        for (const auto & test : cases) {
            const std::string id = test.at("id");
            auto cp = llama_context_default_params();
            cp.n_ctx = test.value("n_ctx", 128);
            cp.n_batch = test.value("n_batch", 128);
            cp.n_ubatch = test.value("n_ubatch", 64);
            cp.n_seq_max = 2;
            cp.kv_unified = true;
            cp.n_threads = 4;
            cp.n_threads_batch = 4;
            cp.type_k = flash ? GGML_TYPE_F16 : GGML_TYPE_F32;
            cp.type_v = cp.type_k;
            cp.flash_attn_type = flash ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
            const auto init_start = clock_type::now();
            std::unique_ptr<llama_context, decltype(&llama_free)> ctx(
                llama_init_from_model(model.get(), cp), llama_free);
            if (!ctx) {
                throw std::runtime_error("context init failed");
            }
            json result = {{"id", id}, {"context_init_ms", elapsed_ms(init_start)},
                           {"n_batch", llama_n_batch(ctx.get())}, {"n_ubatch", llama_n_ubatch(ctx.get())},
                           {"steps", json::array()}};
            int step_id = 0;
            for (const auto & step : test.at("steps")) {
                auto mem = llama_get_memory(ctx.get());
                const int seq = step.value("seq", 0);
                if (step.value("reset", false)) {
                    if (!llama_memory_seq_rm(mem, seq, -1, -1)) {
                        throw std::runtime_error("sequence reset failed");
                    }
                }
                std::vector<llama_token> tokens = step.at("tokens").get<std::vector<llama_token>>();
                const std::string attention = step.at("attention");
                const bool all_logits = step.value("all_logits", true);
                auto batch = llama_batch_init(tokens.size(), 0, 1);
                batch.n_tokens = tokens.size();
                const int pos = step.value("pos", 0);
                for (size_t i = 0; i < tokens.size(); ++i) {
                    batch.token[i] = tokens[i];
                    batch.pos[i] = pos + i;
                    batch.n_seq_id[i] = 1;
                    batch.seq_id[i][0] = seq;
                    batch.logits[i] = all_logits || i + 1 == tokens.size();
                }
                const auto before = llama_memory_seq_pos_max(mem, seq);
                const auto start = clock_type::now();
                int rc;
                {
                    const bool causal = !(variant == "replacement" && prefix_capability && attention == "prefix");
                    causal_scope scope(ctx.get(), causal);
                    rc = llama_decode(ctx.get(), batch);
                    llama_synchronize(ctx.get());
                }
                json entry = {{"return_code", rc}, {"ms", elapsed_ms(start)},
                              {"kv_before", before}, {"kv_after", llama_memory_seq_pos_max(mem, seq)},
                              {"n_tokens", tokens.size()}};
                if (rc == 0) {
                    const std::string file = id + "-" + std::to_string(step_id) + ".f32";
                    std::ofstream binary(out / file, std::ios::binary);
                    int rows = 0;
                    for (size_t i = 0; i < tokens.size(); ++i) {
                        if (!batch.logits[i]) {
                            continue;
                        }
                        const float * row = llama_get_logits_ith(ctx.get(), i);
                        if (!row) {
                            throw std::runtime_error("missing logits");
                        }
                        binary.write(reinterpret_cast<const char *>(row), n_vocab * sizeof(float));
                        ++rows;
                    }
                    if (!binary) {
                        throw std::runtime_error("cannot write logits");
                    }
                    entry["file"] = file;
                    entry["shape"] = {rows, n_vocab};
                }
                llama_batch_free(batch);
                result["steps"].push_back(entry);
                ++step_id;
            }
            report["cases"].push_back(result);
        }
        struct rusage usage;
        getrusage(RUSAGE_SELF, &usage);
#ifdef __APPLE__
        report["process_peak_rss_bytes"] = usage.ru_maxrss;
#else
        report["process_peak_rss_bytes"] = usage.ru_maxrss * 1024;
#endif
        std::ofstream output(out / "result.json");
        output << report.dump(2) << '\n';
        if (!output) {
            throw std::runtime_error("cannot write report");
        }
        return 0;
    } catch (const std::exception & error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
