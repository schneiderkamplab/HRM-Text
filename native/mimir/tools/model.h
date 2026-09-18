#pragma once
#include "llama.h"
#include "ggml-backend.h"
#include <memory>
#include <stdexcept>
#include <string>

namespace mimir::tools {
inline std::shared_ptr<llama_model> load_model(const std::string & path, const std::string & device,
                                               bool vocab_only = false) {
    if (device != "cpu" && device != "metal") { throw std::invalid_argument("device must be cpu or metal"); }
    ggml_backend_dev_t devices[] = {nullptr, nullptr};
    if (device == "metal") {
        for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
            auto dev = ggml_backend_dev_get(i);
            if (std::string(ggml_backend_reg_name(ggml_backend_dev_backend_reg(dev))) == "MTL") {
                devices[0] = dev;
                break;
            }
        }
        if (!devices[0]) { throw std::runtime_error("Metal is unavailable; refusing CPU fallback"); }
    }
    auto params = llama_model_default_params();
    params.devices = devices;
    params.n_gpu_layers = device == "metal" ? 999 : 0;
    params.vocab_only = vocab_only;
    auto model = std::shared_ptr<llama_model>(llama_model_load_from_file(path.c_str(), params), llama_model_free);
    if (!model) { throw std::runtime_error("cannot load model: " + path); }
    return model;
}
} // namespace mimir::tools
