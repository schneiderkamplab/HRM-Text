#pragma once
#include "ggml-backend.h"
#include "llama.h"
#include <stdexcept>
#include <vector>
#include "mimir_ffi.h"
#ifdef MIMIR_DYNAMIC_BACKENDS
#include <filesystem>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <dlfcn.h>
#endif
#endif
namespace mimir::runtime {
inline void initialize_backends() {
#ifdef MIMIR_DYNAMIC_BACKENDS
    // Resolve the loaded runtime itself; never search the caller's working directory.
    std::filesystem::path library;
#ifdef _WIN32
    HMODULE module = nullptr;
    if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        reinterpret_cast<LPCWSTR>(&mimir_create), &module)) { throw std::runtime_error("Cannot locate native runtime"); }
    std::vector<wchar_t> path(32768);
    const auto length = GetModuleFileNameW(module, path.data(), DWORD(path.size()));
    if (!length || length >= path.size()) { throw std::runtime_error("Cannot locate native runtime path"); }
    library = std::wstring(path.data(), length);
#else
    Dl_info info{};
    if (!dladdr(reinterpret_cast<void *>(&mimir_create), &info) || !info.dli_fname) {
        throw std::runtime_error("Cannot locate native runtime");
    }
    library = info.dli_fname;
#endif
    const auto directory = std::filesystem::absolute(library).parent_path().u8string();
    ggml_backend_load_all_from_path(directory.c_str());
#else
    ggml_backend_load_all();
#endif
    if (!ggml_backend_dev_by_type(GGML_BACKEND_DEVICE_TYPE_CPU)) {
        throw std::runtime_error("The packaged CPU backend is missing or incompatible. Reinstall the app.");
    }
    llama_backend_init();
}
}
