#include "mimir/chat.h"
#include "utf8.h"
#include <algorithm>

namespace mimir {
Chat::Chat(std::shared_ptr<llama_model> model, Config config, std::string system)
    : codec_(model), session_(std::move(model), config), system_(std::move(system)) {
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

void Chat::reset() {
    recover();
    history_.clear();
    if (!system_.empty()) { history_.push_back({"system", system_}); }
}

Reply Chat::reply(const std::string & user, uint32_t max_tokens,
                  const std::function<void(const std::string &)> & stream) {
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
        if (!next) {
            reply.status = next.status;
            reply.finish = next.status == Status::cancelled ? Finish::cancelled : Finish::error;
            return reply;
        }
        for (uint32_t i = 0; i < max_tokens; ++i) {
            if (cancelled_.load(std::memory_order_relaxed)) { break; }
            // Greedy sampling is intentionally deterministic for the first text path.
            const auto token = llama_token(std::max_element(next.logits.begin(), next.logits.end()) - next.logits.begin());
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
