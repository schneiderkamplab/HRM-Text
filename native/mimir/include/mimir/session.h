#pragma once

#include "llama.h"

#include <atomic>
#include <cstdint>
#include <memory>
#include <vector>

namespace mimir {

enum class Status { ok, invalid_input, capacity, not_ready, cancelled, backend_error };

struct Result {
    Status status = Status::ok;
    int backend_code = 0;
    // Owned row-major logits. Normally one row; all_logits requests one per input token.
    std::vector<float> logits;
    uint32_t reused_tokens = 0;
    explicit operator bool() const noexcept { return status == Status::ok; }
};

struct Config {
    uint32_t context_tokens = 2048;
    uint32_t batch_tokens = 1024;
    int threads = 4;
    bool flash_attention = false;
    ggml_type cache_type = GGML_TYPE_F16;
    bool allow_context_extension = false; // Opt in to positions beyond the training context.
    bool mixed_lm = false; // Approximate frozen-prefix reuse; PrefixLM only.
};

// Initialize llama backends before loading the shared model. The session owns its context.
// All methods require serialized access, except request_cancel(), which is thread-safe.
// Do not destroy a session while a method or request_cancel() is running.
class Session final {
public:
    Session(std::shared_ptr<llama_model> model, Config config);
    ~Session();
    Session(const Session &) = delete;
    Session & operator=(const Session &) = delete;
    Session(Session &&) = delete;
    Session & operator=(Session &&) = delete;

    // Supply the entire rendered conversation, including the assistant generation header.
    // By default each begin discards KV and makes the complete PrefixLM prompt bidirectional.
    // MixedLM retains the previous prompt KV only when its tokens match exactly, and
    // recomputes the suffix bidirectionally. Ordinary causal models use causal processing.
    // Reserve a positive answer budget; prompt + budget must fit the configured context.
    Result begin_turn(const std::vector<llama_token> & prompt, uint32_t answer_budget, bool all_logits = false);
    Result append(const std::vector<llama_token> & answer, bool all_logits = false);

    // Cancellation is sticky until reset(). CPU can abort within a decode; other backends
    // may finish that decode. Cancelled results are discarded and the session is cleared.
    void request_cancel() noexcept;
    void reset();
    uint32_t position() const noexcept { return position_; }
    uint32_t remaining() const noexcept { return remaining_; }
    bool ready() const noexcept { return ready_; }
    bool prefix_lm() const noexcept { return prefix_lm_; }

private:
    friend struct SessionTestPeer;
    static bool abort_requested(void * data);
    Status validate(const std::vector<llama_token> & tokens) const;
    Result execute(const std::vector<llama_token> & tokens, bool prefix, bool all_logits, bool mixed = false);
    void invalidate();

    std::shared_ptr<llama_model> model_;
    std::unique_ptr<llama_context, decltype(&llama_free)> context_{nullptr, llama_free};
    Config config_;
    std::atomic<bool> cancelled_{false};
    uint32_t position_ = 0;
    uint32_t remaining_ = 0;
    bool ready_ = false;
    bool prefix_lm_ = false;
    int32_t vocab_size_ = 0;
    std::vector<llama_token> prefix_tokens_;
    // Private seam for deterministic tests of failures after partial KV writes.
    int32_t (*decode_)(llama_context *, llama_batch) = nullptr;
};

} // namespace mimir
