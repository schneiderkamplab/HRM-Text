#pragma once
#include "llama.h"
#include "mimir/backend_policy.h"
#include "ggml-backend.h"
#include <algorithm>
#include <cctype>
#include <memory>
#include <stdexcept>
#include <string>

namespace mimir::tools {
inline std::string device_key(std::string value) { return backend_key(std::move(value)); }
inline std::vector<BackendCandidate> available_devices() {
    std::vector<BackendCandidate> result;
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        auto dev = ggml_backend_dev_get(i);
        auto type = ggml_backend_dev_type(dev);
        result.push_back({ggml_backend_dev_name(dev), ggml_backend_reg_name(ggml_backend_dev_backend_reg(dev)),
                          type == GGML_BACKEND_DEVICE_TYPE_GPU || type == GGML_BACKEND_DEVICE_TYPE_IGPU || type == GGML_BACKEND_DEVICE_TYPE_ACCEL});
    }
    return result;
}
inline ggml_backend_dev_t select_device(const std::string & requested) {
    const auto candidate = backend_candidates(available_devices(), requested).front();
    if (device_key(candidate.id) == "cpu") { return nullptr; }
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        auto dev = ggml_backend_dev_get(i);
        if (candidate.id == ggml_backend_dev_name(dev)) { return dev; }
    }
    throw std::invalid_argument("Device disappeared: " + requested);
}
inline std::shared_ptr<llama_model> load_model(const std::string & path, const std::string & device,
                                               bool vocab_only = false) {
    if (device_key(device) == "auto" && !vocab_only) {
        // Metadata failures are not accelerator failures.
        load_model(path, "cpu", true);
        std::shared_ptr<llama_model> loaded;
        std::vector<std::string> failures;
        try_backends(backend_candidates(available_devices(), device), [&](const auto & candidate) {
            loaded = load_model(path, candidate.id);
        }, failures);
        return loaded;
    }
    auto selected = select_device(device);
    ggml_backend_dev_t devices[] = {selected, nullptr};
    auto params = llama_model_default_params();
    params.devices = devices;
    params.n_gpu_layers = selected && ggml_backend_dev_type(selected) != GGML_BACKEND_DEVICE_TYPE_CPU ? 999 : 0;
    params.vocab_only = vocab_only;
    auto model = std::shared_ptr<llama_model>(llama_model_load_from_file(path.c_str(), params), llama_model_free);
    if (!model) { throw BackendFailure("cannot load model: " + path); }
    return model;
}
} // namespace mimir::tools
