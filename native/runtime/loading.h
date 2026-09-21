#pragma once
#include "mimir/chat.h"
#include "model.h"
#include "platform_memory.h"
#include "nlohmann/json.hpp"
#include <cmath>

namespace mimir::runtime {
using Json = nlohmann::json;
struct Loaded {
    std::shared_ptr<llama_model> model;
    std::unique_ptr<TextCodec> codec;
    std::shared_ptr<Chat> chat;
    BackendCandidate device;
    std::vector<std::string> failures;
    int context = 0;
    bool flash = false;
};
inline Loaded load(const Json & command) {
    const auto & profile = command.at("profile");
    const auto path = command.at("path").get<std::string>();
    const auto requested = command.value("device", std::string("auto"));
    const int minimum = profile.at("minimumContext"), maximum = profile.at("maximumContext");
    const int explicit_context = command.value("context", 0), threads = profile.at("threads");
    const double fraction = profile.at("memoryFraction");
    if (minimum < 1 || maximum < minimum || threads < 1 || threads > 256 || !std::isfinite(fraction) || fraction <= 0 || fraction > 1 ||
        (explicit_context && (explicit_context < minimum || explicit_context > maximum))) {
        throw std::invalid_argument("Invalid model profile or context limits.");
    }
    const auto candidates = backend_candidates(tools::available_devices(), requested);
    const std::string system = profile.at("systemPrompt");
    // Reject invalid files, metadata and chat templates once, before accelerator retries.
    {
        auto metadata = tools::load_model(path, "cpu", true);
        char architecture[64]{};
        llama_model_meta_val_str(metadata.get(), "general.architecture", architecture, sizeof architecture);
        char prefix[16]{};
        llama_model_meta_val_str(metadata.get(), "hrm_text.hrm.prefix_lm", prefix, sizeof prefix);
        if (std::string(architecture) != "hrm_text" || std::string(prefix) != "true") {
            throw std::invalid_argument("Choose a PrefixLM HRMText Mimir GGUF.");
        }
        TextCodec check(metadata);
        check.prepare({{"system", system}, {"user", "test"}});
    }
    Loaded result;
    const auto host_available = available_memory();
    result.device = try_backends(candidates, [&](const BackendCandidate & candidate) {
        auto selected = tools::select_device(candidate.id);
        const bool gpu = selected && (ggml_backend_dev_type(selected) == GGML_BACKEND_DEVICE_TYPE_GPU ||
                                      ggml_backend_dev_type(selected) == GGML_BACKEND_DEVICE_TYPE_IGPU);
        uint64_t available = host_available;
        if (selected && ggml_backend_dev_type(selected) == GGML_BACKEND_DEVICE_TYPE_GPU) {
            size_t free = 0, total = 0; ggml_backend_dev_memory(selected, &free, &total);
            if (free) { available = std::min(available, uint64_t(free)); }
        }
        const auto choose_context = [&](bool flash) {
            int context = explicit_context ? explicit_context : minimum;
            if (!explicit_context) {
                for (int tier : profile.at("contextTiers")) {
                    if (tier < minimum || tier > maximum) { throw std::invalid_argument("Invalid context tier."); }
                    const long double required = command.at("modelBytes").get<uint64_t>() +
                        profile.at("fixedMemoryBytes").get<uint64_t>() +
                        (long double)tier * profile.at("memoryBytesPerToken").get<uint64_t>() +
                        (flash ? 0 : (long double)tier * tier * profile.at("cpuAttentionBytesPerTokenSquared").get<uint64_t>());
                    if (required <= available * fraction) { context = std::max(context, tier); }
                }
            }
            return context;
        };
        // Local ownership releases failed models/contexts before the next attempt.
        auto model = tools::load_model(path, candidate.id);
        Config config;
        config.flash_attention = command.value("flash", gpu);
        config.context_tokens = config.batch_tokens = choose_context(config.flash_attention);
        config.threads = threads; config.allow_context_extension = true;
        config.mixed_lm = command.value("mixedLM", false);
        std::shared_ptr<Chat> chat;
        try { chat = std::make_shared<Chat>(model, config, system); }
        catch (const std::runtime_error & e) {
            if (!candidate.accelerator || command.contains("flash") || !config.flash_attention) { throw BackendFailure(e.what()); }
            result.failures.push_back(candidate.id + ": context with flash attention failed; retrying without flash attention");
            config.flash_attention = false;
            config.context_tokens = config.batch_tokens = choose_context(false);
            try { chat = std::make_shared<Chat>(model, config, system); }
            catch (const std::runtime_error & retry) { throw BackendFailure(retry.what()); }
        }
        auto codec = std::make_unique<TextCodec>(model);
        result.model = std::move(model); result.chat = std::move(chat); result.codec = std::move(codec);
        result.context = config.context_tokens; result.flash = config.flash_attention;
    }, result.failures);
    return result;
}
} // namespace mimir::runtime
