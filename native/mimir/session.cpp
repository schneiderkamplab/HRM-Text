#include "mimir/session.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace mimir {
Session::Session(std::shared_ptr<llama_model> model, Config config)
    : model_(std::move(model)), config_(config) {
    if (!model_ || !config.context_tokens || !config.batch_tokens || config.threads <= 0 ||
        config.batch_tokens > config.context_tokens ||
        config.context_tokens > uint32_t(std::numeric_limits<int32_t>::max()) ||
        config.context_tokens > uint32_t(llama_model_n_ctx_train(model_.get())) ||
        (config.cache_type != GGML_TYPE_F32 && config.cache_type != GGML_TYPE_F16) ||
        !llama_model_has_decoder(model_.get()) || llama_model_has_encoder(model_.get()) ||
        llama_model_is_recurrent(model_.get()) || llama_model_is_diffusion(model_.get())) {
        throw std::invalid_argument("unsupported model or session configuration");
    }
    prefix_lm_ = llama_model_is_prefix_lm(model_.get());
    vocab_size_ = llama_vocab_n_tokens(llama_model_get_vocab(model_.get()));
    if (vocab_size_ <= 0) {
        throw std::invalid_argument("model has no token vocabulary size");
    }
    auto params = llama_context_default_params();
    params.n_ctx = config.context_tokens;
    params.n_batch = params.n_ubatch = config.batch_tokens;
    params.n_seq_max = 1;
    params.n_threads = params.n_threads_batch = config.threads;
    params.type_k = params.type_v = config.cache_type;
    params.flash_attn_type = config.flash_attention ? LLAMA_FLASH_ATTN_TYPE_ENABLED : LLAMA_FLASH_ATTN_TYPE_DISABLED;
    params.abort_callback = abort_requested;
    params.abort_callback_data = this;
    context_.reset(llama_init_from_model(model_.get(), params));
    if (!context_ || !llama_get_memory(context_.get())) {
        throw std::runtime_error("failed to allocate a session context with KV memory");
    }
    if (llama_n_ctx_seq(context_.get()) < config.context_tokens ||
        llama_n_ubatch(context_.get()) < config.batch_tokens ||
        llama_n_batch(context_.get()) < config.batch_tokens) {
        throw std::runtime_error("runtime capacities are smaller than requested");
    }
}

Session::~Session() = default;

bool Session::abort_requested(void * data) {
    return static_cast<Session *>(data)->cancelled_.load(std::memory_order_relaxed);
}

void Session::request_cancel() noexcept {
    cancelled_.store(true, std::memory_order_relaxed);
}

void Session::invalidate() {
    llama_synchronize(context_.get());
    llama_memory_clear(llama_get_memory(context_.get()), true);
    position_ = remaining_ = 0;
    ready_ = false;
}

void Session::reset() {
    invalidate();
    cancelled_.store(false, std::memory_order_relaxed);
}

Status Session::validate(const std::vector<llama_token> & tokens) const {
    if (tokens.empty() || std::any_of(tokens.begin(), tokens.end(), [this](llama_token token) {
            return token < 0 || token >= vocab_size_;
        })) {
        return Status::invalid_input;
    }
    return tokens.size() > config_.batch_tokens ? Status::capacity : Status::ok;
}

Result Session::begin_turn(const std::vector<llama_token> & prompt, uint32_t answer_budget, bool all_logits) {
    if (abort_requested(this)) {
        invalidate();
        return {Status::cancelled, 0, {}};
    }
    auto status = validate(prompt);
    if (status != Status::ok) {
        return {status, 0, {}};
    }
    if (!answer_budget) {
        return {Status::invalid_input, 0, {}};
    }
    if (uint64_t(prompt.size()) + answer_budget > config_.context_tokens) {
        return {Status::capacity, 0, {}};
    }
    if (prefix_lm_) {
        position_ = remaining_ = 0;
        ready_ = false;
    } else {
        invalidate();
    }
    auto result = execute(prompt, prefix_lm_, all_logits);
    if (result) {
        remaining_ = answer_budget;
        ready_ = true;
    }
    return result;
}

Result Session::append(const std::vector<llama_token> & answer, bool all_logits) {
    if (abort_requested(this)) {
        invalidate();
        return {Status::cancelled, 0, {}};
    }
    if (!ready_) {
        return {Status::not_ready, 0, {}};
    }
    auto status = validate(answer);
    if (status != Status::ok) {
        return {status, 0, {}};
    }
    if (answer.size() > remaining_) {
        return {Status::capacity, 0, {}};
    }
    auto result = execute(answer, false, all_logits);
    if (result) {
        remaining_ -= uint32_t(answer.size());
    }
    return result;
}

Result Session::execute(const std::vector<llama_token> & tokens, bool prefix, bool all_logits) {
    // Allocate host buffers before entering the backend. Any exception invalidates KV.
    try {
        const size_t rows = all_logits ? tokens.size() : 1;
        if (rows > std::numeric_limits<size_t>::max() / size_t(vocab_size_)) {
            throw std::length_error("logits allocation overflow");
        }
        Result result;
        result.logits.resize(rows * size_t(vocab_size_));
        std::vector<llama_pos> positions(tokens.size());
        std::vector<int32_t> counts(tokens.size(), 1);
        llama_seq_id sequence = 0;
        std::vector<llama_seq_id *> sequences(tokens.size(), &sequence);
        std::vector<int8_t> outputs(tokens.size(), all_logits ? 1 : 0);
        outputs.back() = 1;
        for (size_t i = 0; i < tokens.size(); ++i) {
            positions[i] = llama_pos(position_ + i);
        }
        llama_batch batch{int32_t(tokens.size()), const_cast<llama_token *>(tokens.data()), nullptr,
                          positions.data(), counts.data(), sequences.data(), outputs.data()};
        {
            result.backend_code = decode_ ? decode_(context_.get(), batch) :
                prefix ? llama_decode_prefix(context_.get(), batch) : llama_decode(context_.get(), batch);
            llama_synchronize(context_.get());
        }
        const bool cancelled = abort_requested(this) || result.backend_code == 2;
        if (cancelled || result.backend_code != 0) {
            if (cancelled) {
                request_cancel();
            }
            invalidate();
            return {cancelled ? Status::cancelled : Status::backend_error, result.backend_code, {}};
        }
        for (size_t row = 0; row < rows; ++row) {
            const int32_t index = int32_t(all_logits ? row : tokens.size() - 1);
            const float * logits = llama_get_logits_ith(context_.get(), index);
            if (!logits || !std::all_of(logits, logits + vocab_size_, [](float x) { return std::isfinite(x); })) {
                invalidate();
                return {Status::backend_error, -3, {}};
            }
            std::copy(logits, logits + vocab_size_, result.logits.begin() + row * vocab_size_);
        }
        if (abort_requested(this)) {
            invalidate();
            return {Status::cancelled, 0, {}};
        }
        position_ += uint32_t(tokens.size());
        return result;
    } catch (...) {
        invalidate();
        throw;
    }
}

} // namespace mimir
