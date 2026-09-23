#pragma once
#include "session.h"
#include <functional>
#include <string>

namespace mimir {

struct Message { std::string role; std::string content; std::string tool_context = {}; };
struct Prompt { std::string text; std::vector<llama_token> tokens; };

// Uses the GGUF's exact template and vocabulary. Only text messages are supported.
class TextCodec {
public:
    explicit TextCodec(std::shared_ptr<llama_model> model);
    ~TextCodec();
    Prompt prepare(const std::vector<Message> & messages, bool generation_prompt = true) const;
    std::vector<llama_token> tokenize(const std::string & text, bool add_special = false) const;
    std::string piece(llama_token token, bool special = false) const;
    void set_tools(const std::string & tools);
    std::string decode(const std::vector<llama_token> & tokens) const;
    bool is_end(llama_token token) const;
private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

struct Sampling { float temperature = 0; float top_p = 1; uint32_t seed = 0; float repeat_penalty = 1; };

enum class Finish { eos, length, cancelled, error, tool_call };
struct Reply {
    Status status = Status::ok;
    Finish finish = Finish::length;
    std::string text;
    std::vector<llama_token> tokens;
    llama_token stop_token = LLAMA_TOKEN_NULL;
    uint32_t reused_tokens = 0;
};

// Serialize all methods except request_cancel(). Failed/cancelled turns do not
// enter history. Call recover() after joining cancellation producers to resume.
class Chat {
public:
    Chat(std::shared_ptr<llama_model> model, Config config, std::string system = "");
    Reply reply(const std::string & user, uint32_t max_tokens,
                const std::function<void(const std::string &)> & stream = {}, Sampling sampling = {},
                const std::string & tool_context = "");
    void request_cancel() noexcept;
    bool cancelled() const noexcept { return cancelled_.load(std::memory_order_relaxed); }
    void recover(); // Clears runtime/cancellation, retaining completed history.
    void set_system(const std::string & system);
    void set_tools(const std::string & tools);
    void reset();   // Starts a new conversation, retaining the system message.
    // Restore completed user/assistant pairs; validates before replacing history.
    // preserve_cache skips reset only if the validated history is identical.
    void restore_history(const std::vector<Message> & messages, bool preserve_cache = false);
    static void validate_history(const std::vector<Message> & messages);
    const std::vector<Message> & history() const noexcept { return history_; }
private:
    int32_t n_vocab_;
    TextCodec codec_;
    Session session_;
    std::string system_, tools_;
    std::vector<Message> history_;
    std::atomic<bool> cancelled_{false};
};

} // namespace mimir
