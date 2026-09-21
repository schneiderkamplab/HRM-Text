// Run against the APK's runtime on Android, before any model allocation.
#include "mimir_ffi.h"
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

std::string command(void * engine, const char * json) {
    if (mimir_submit(engine, json) != 1) throw std::runtime_error("submit failed");
    std::string result;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(20);
    while (std::chrono::steady_clock::now() < deadline) {
        if (auto event = mimir_poll(engine)) {
            std::string text(event);
            mimir_free(event);
            result += text;
            if (text.find("\"type\":\"done\"") != std::string::npos) return result;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    throw std::runtime_error("native operation timed out");
}
int main() {
    auto engine = mimir_create();
    if (!engine) return 1;
    try {
        const auto devices = command(engine, "{\"op\":\"devices\"}");
        if (devices.find("\"id\":\"cpu\"") == std::string::npos ||
            devices.find("Vulkan") != std::string::npos ||
            devices.find("\"type\":\"error\"") != std::string::npos ||
            !std::getenv("GGML_DISABLE_VULKAN")) throw std::runtime_error("CPU session touched Vulkan");
        const auto switched = command(engine, "{\"op\":\"load\",\"device\":\"vulkan\"}");
        if (switched.find("force-stopping") == std::string::npos) throw std::runtime_error("Backend switch was not rejected");
        mimir_destroy(engine);
        std::cout << "Android CPU registry and restart guard passed\n";
    } catch (const std::exception & e) {
        std::cerr << e.what() << '\n';
        std::exit(1); // A stuck driver cannot safely be joined during teardown.
    }
}
