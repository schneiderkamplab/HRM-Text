#include "mimir/chat.h"
#include "utf8.h"
#include "jinja/parser.h"
#include "jinja/runtime.h"
#include "json.h"
#include <limits>
#include <stdexcept>

namespace mimir {
struct TextCodec::Impl {
    std::shared_ptr<llama_model> model;
    const llama_vocab * vocab;
    std::string source;
    jinja::program program;

    explicit Impl(std::shared_ptr<llama_model> owner) : model(std::move(owner)) {
        if (!model) { throw std::invalid_argument("missing model"); }
        vocab = llama_model_get_vocab(model.get());
        const char * template_text = llama_model_chat_template(model.get(), nullptr);
        if (!template_text || !*template_text || llama_vocab_type(vocab) == LLAMA_VOCAB_TYPE_NONE ||
            llama_vocab_bos(vocab) == LLAMA_TOKEN_NULL || llama_vocab_eos(vocab) == LLAMA_TOKEN_NULL) {
            throw std::invalid_argument("GGUF needs a tokenizer, BOS/EOS, and chat template");
        }
        source = template_text;
        jinja::lexer lexer;
        program = jinja::parse_from_tokens(lexer.tokenize(source));
    }
};

TextCodec::TextCodec(std::shared_ptr<llama_model> model) : impl_(new Impl(std::move(model))) {}
TextCodec::~TextCodec() = default;

std::vector<llama_token> TextCodec::tokenize(const std::string & text, bool add_special) const {
    detail::require_utf8(text);
    if (text.size() > size_t(std::numeric_limits<int32_t>::max())) {
        throw std::length_error("text too long");
    }
    const auto size = int32_t(text.size());
    const auto count = llama_tokenize(impl_->vocab, text.data(), size, nullptr, 0, add_special, true);
    if (count == INT32_MIN) { throw std::length_error("tokenization overflow"); }
    std::vector<llama_token> tokens(count < 0 ? -count : count);
    const auto actual = llama_tokenize(impl_->vocab, text.data(), size, tokens.data(), tokens.size(), add_special, true);
    if (actual < 0) { throw std::runtime_error("tokenization failed"); }
    tokens.resize(actual);
    return tokens;
}

Prompt TextCodec::prepare(const std::vector<Message> & messages, bool generation_prompt) const {
    if (messages.empty()) { throw std::invalid_argument("messages cannot be empty"); }
    common_json values = common_json::array();
    for (size_t i = 0; i < messages.size(); ++i) {
        const auto & message = messages[i];
        if (message.role != "user" && message.role != "assistant" && !(i == 0 && message.role == "system")) {
            throw std::invalid_argument("supported roles: initial system, user, assistant");
        }
        detail::require_utf8(message.content);
        values.push_back({{"role", message.role}, {"content", message.content}});
    }
    jinja::context context(impl_->source);
    const common_json vars = {{"messages", values}, {"add_generation_prompt", generation_prompt},
        {"bos_token", llama_vocab_get_text(impl_->vocab, llama_vocab_bos(impl_->vocab))},
        {"eos_token", llama_vocab_get_text(impl_->vocab, llama_vocab_eos(impl_->vocab))},
        {"enable_thinking", false}};
    jinja::global_from_json(context, vars, true);
    jinja::runtime runtime(context);
    auto text = runtime.gather_string_parts(runtime.execute(impl_->program))->as_string().str();
    return {text, tokenize(text, false)}; // The template already supplies BOS.
}

std::string TextCodec::piece(llama_token token) const {
    if (token < 0 || token >= llama_vocab_n_tokens(impl_->vocab)) {
        throw std::invalid_argument("token outside vocabulary");
    }
    std::string text(128, '\0');
    int count = llama_token_to_piece(impl_->vocab, token, text.data(), text.size(), 0, false);
    if (count < 0) {
        text.resize(-count);
        count = llama_token_to_piece(impl_->vocab, token, text.data(), text.size(), 0, false);
    }
    if (count < 0) { throw std::runtime_error("detokenization failed"); }
    text.resize(count);
    return text;
}

std::string TextCodec::decode(const std::vector<llama_token> & tokens) const {
    detail::Utf8Stream stream;
    std::string text;
    for (const auto token : tokens) { text += stream.push(piece(token)); }
    return text + stream.push("", true);
}

bool TextCodec::is_end(llama_token token) const { return token == llama_vocab_eos(impl_->vocab); }
} // namespace mimir
