#pragma once
#include "llama.h"
#include "ggml-backend.h"
#include <algorithm>
#include <cctype>
#include <memory>
#include <stdexcept>
#include <string>

namespace mimir::tools {
inline std::string device_key(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    return value;
}
// Backend names or exact device names come from ggml, not a platform whitelist.
inline ggml_backend_dev_t select_device(const std::string & requested) {
    auto key = device_key(requested);
    if (key == "metal") { key = "mtl"; }
    if (key == "cpu") { return nullptr; }
    ggml_backend_dev_t first_gpu = nullptr, backend_match = nullptr;
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        auto dev = ggml_backend_dev_get(i);
        const auto type = ggml_backend_dev_type(dev);
        if (!first_gpu && (type == GGML_BACKEND_DEVICE_TYPE_GPU || type == GGML_BACKEND_DEVICE_TYPE_IGPU)) { first_gpu = dev; }
        if (key == device_key(ggml_backend_dev_name(dev))) { return dev; }
        if (!backend_match && key == device_key(ggml_backend_reg_name(ggml_backend_dev_backend_reg(dev)))) { backend_match = dev; }
    }
    if (key == "auto") { return first_gpu; }
    if (backend_match) { return backend_match; }
    throw std::invalid_argument("Requested backend/device is unavailable: " + requested + ". Use --list-devices. No automatic CPU fallback was made.");
}
inline std::shared_ptr<llama_model> load_model(const std::string & path, const std::string & device,
                                               bool vocab_only = false) {
    auto selected = select_device(device);
    ggml_backend_dev_t devices[] = {selected, nullptr};
    auto params = llama_model_default_params();
    params.devices = devices;
    params.n_gpu_layers = selected && ggml_backend_dev_type(selected) != GGML_BACKEND_DEVICE_TYPE_CPU ? 999 : 0;
    params.vocab_only = vocab_only;
    auto model = std::shared_ptr<llama_model>(llama_model_load_from_file(path.c_str(), params), llama_model_free);
    if (!model) { throw std::runtime_error("cannot load model: " + path); }
    return model;
}
} // namespace mimir::tools
