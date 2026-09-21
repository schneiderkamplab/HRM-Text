#pragma once
#include <algorithm>
#include <cctype>
#include <stdexcept>
#include <string>
#include <vector>

namespace mimir {
// Only this failure category is retryable. Invalid input and cancellation escape.
class BackendFailure : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};
struct BackendCandidate {
    std::string id, backend;
    bool accelerator = false;
};
inline std::string backend_key(std::string text) {
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char c) { return char(std::tolower(c)); });
    return text == "metal" ? "mtl" : text;
}
inline std::vector<BackendCandidate> backend_candidates(std::vector<BackendCandidate> devices, const std::string & requested) {
    const auto key = backend_key(requested);
    if (key == "cpu") { return {{"CPU", "CPU", false}}; }
    if (key != "auto") {
        for (const auto & d : devices) { if (backend_key(d.id) == key) { return {d}; } }
        for (const auto & d : devices) { if (backend_key(d.backend) == key) { return {d}; } }
        throw std::invalid_argument("Requested backend/device is unavailable: " + requested + ". Select Automatic or CPU.");
    }
    devices.erase(std::remove_if(devices.begin(), devices.end(), [](const auto & d) { return !d.accelerator; }), devices.end());
    const auto rank = [](const BackendCandidate & d) {
        const auto name = backend_key(d.backend);
        return name == "mtl" ? 0 : name == "cuda" ? 10 : name == "vulkan" ? 20 : 30;
    };
    std::stable_sort(devices.begin(), devices.end(), [&](const auto & a, const auto & b) { return rank(a) < rank(b); });
    devices.push_back({"CPU", "CPU", false});
    return devices;
}
// Each failed attempt must release its resources before throwing. Explicit selection
// never silently changes devices. Reasons also survive when all candidates fail.
template<class Attempt>
BackendCandidate try_backends(const std::vector<BackendCandidate> & candidates, Attempt attempt,
                               std::vector<std::string> & failures) {
    for (const auto & candidate : candidates) {
        try { attempt(candidate); return candidate; }
        catch (const BackendFailure & e) { failures.push_back(candidate.id + ": " + e.what()); }
    }
    std::string message = "No compute device could initialize the model.";
    for (const auto & failure : failures) { message += "\n" + failure; }
    throw BackendFailure(message);
}
} // namespace mimir
