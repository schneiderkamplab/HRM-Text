#include "mimir/chat.h"
#include "utf8.h"
#include <algorithm>
#include <stdexcept>
#include <cmath>

namespace mimir {
Chat::Chat(std::shared_ptr<llama_model> model, Config config, std::string system)
    : n_vocab_(llama_vocab_n_tokens(llama_model_get_vocab(model.get()))), codec_(model), session_(std::move(model), config), system_(std::move(system)) {
    detail::require_utf8(system_);
    if (!system_.empty()) { history_.push_back({"system", system_}); }
}

void Chat::request_cancel() noexcept {
    cancelled_.store(true, std::memory_order_relaxed);
    session_.request_cancel();
}

void Chat::recover() {
    session_.reset();
    cancelled_.store(false, std::memory_order_relaxed);
}

void Chat::set_system(const std::string & system) {
    detail::require_utf8(system);
    system_ = system;
    reset();
}

void Chat::reset() {
    recover();
    history_.clear();
    if (!system_.empty()) { history_.push_back({"system", system_}); }
}

void Chat::validate_history(const std::vector<Message> & messages) {
    if (messages.size() % 2 != 0) { throw std::invalid_argument("history needs completed turn pairs"); }
    for (size_t i = 0; i < messages.size(); ++i) {
        if (messages[i].role != (i % 2 ? "assistant" : "user")) {
            throw std::invalid_argument("history must alternate user and assistant");
        }
        detail::require_utf8(messages[i].content);
    }
}

void Chat::restore_history(const std::vector<Message> & messages, bool preserve_cache) {
    validate_history(messages);
    auto candidate = std::vector<Message>{};
    if (!system_.empty()) { candidate.push_back({"system", system_}); }
    candidate.insert(candidate.end(), messages.begin(), messages.end());
    if (preserve_cache && candidate.size() == history_.size() &&
        std::equal(candidate.begin(), candidate.end(), history_.begin(), [](const Message & a, const Message & b) {
            return a.role == b.role && a.content == b.content;
        })) { return; }
    reset();
    history_ = std::move(candidate);
}

Reply Chat::reply(const std::string & user, uint32_t max_tokens,
                  const std::function<void(const std::string &)> & stream, Sampling sampling) {
    if (!std::isfinite(sampling.temperature) || sampling.temperature < 0 || sampling.temperature > 2 ||
        !std::isfinite(sampling.top_p) || sampling.top_p <= 0 || sampling.top_p > 1 ||
        !std::isfinite(sampling.repeat_penalty) || sampling.repeat_penalty < 1 || sampling.repeat_penalty > 2) {
        throw std::invalid_argument("Invalid sampling parameters");
    }
    auto sampler = std::unique_ptr<llama_sampler, decltype(&llama_sampler_free)>(
        llama_sampler_chain_init(llama_sampler_chain_default_params()), llama_sampler_free);
    if (sampling.repeat_penalty != 1) {
        // Track only tokens generated in this reply; the chain resets each turn.
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_penalties(n_vocab_, 64, sampling.repeat_penalty, 0, 0));
    }
    if (sampling.temperature > 0) {
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_top_p(sampling.top_p, 1));
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_temp(sampling.temperature));
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_dist(sampling.seed));
    } else {
        llama_sampler_chain_add(sampler.get(), llama_sampler_init_greedy());
    }
    if (cancelled_.load(std::memory_order_relaxed)) {
        Reply reply;
        reply.status = Status::cancelled;
        reply.finish = Finish::cancelled;
        return reply;
    }
    auto candidate = history_;
    candidate.push_back({"user", user});
    const auto prompt = codec_.prepare(candidate);
    Reply reply;
    detail::Utf8Stream utf8;
    auto emit = [&](const std::string & text) {
        reply.text += text;
        if (stream && !text.empty()) { stream(text); }
    };
    try {
        auto next = session_.begin_turn(prompt.tokens, max_tokens);
        reply.reused_tokens = next.reused_tokens;
        if (!next) {
            reply.status = next.status;
            reply.finish = next.status == Status::cancelled ? Finish::cancelled : Finish::error;
            return reply;
        }
        for (uint32_t i = 0; i < max_tokens; ++i) {
            if (cancelled_.load(std::memory_order_relaxed)) { break; }
            std::vector<llama_token_data> candidates;
            candidates.reserve(next.logits.size());
            for (size_t j = 0; j < next.logits.size(); ++j) candidates.push_back({llama_token(j), next.logits[j], 0});
            llama_token_data_array probabilities{candidates.data(), candidates.size(), -1, false};
            llama_sampler_apply(sampler.get(), &probabilities);
            const auto token = probabilities.data[probabilities.selected].id;
            llama_sampler_accept(sampler.get(), token);
            if (codec_.is_end(token)) {
                reply.finish = Finish::eos;
                reply.stop_token = token;
                break;
            }
            next = session_.append({token});
            if (!next) {
                reply.status = next.status;
                reply.finish = next.status == Status::cancelled ? Finish::cancelled : Finish::error;
                return reply;
            }
            reply.tokens.push_back(token);
            emit(utf8.push(codec_.piece(token)));
        }
        if (!cancelled_.load(std::memory_order_relaxed)) {
            emit(utf8.push("", true));
        }
        if (cancelled_.load(std::memory_order_relaxed)) {
            session_.reset();
            session_.request_cancel();
            reply.status = Status::cancelled;
            reply.finish = Finish::cancelled;
            return reply;
        }
        candidate.push_back({"assistant", reply.text});
        history_ = std::move(candidate);
        return reply;
    } catch (...) {
        session_.reset();
        throw;
    }
}
} // namespace mimir
