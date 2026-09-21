#pragma once
#include <stdexcept>
#include <string>

namespace mimir::detail {

// Retains incomplete code points between token pieces. Invalid bytes are replaced.
class Utf8Stream {
public:
    std::string push(const std::string & bytes, bool final = false) {
        pending_ += bytes;
        std::string out;
        size_t offset = 0;
        while (offset < pending_.size()) {
            const auto c = static_cast<unsigned char>(pending_[offset]);
            size_t length = c < 0x80 ? 1 : c >= 0xc2 && c <= 0xdf ? 2 :
                            c >= 0xe0 && c <= 0xef ? 3 : c >= 0xf0 && c <= 0xf4 ? 4 : 0;
            size_t valid = 1;
            for (; length && valid < length && offset + valid < pending_.size(); ++valid) {
                auto next = static_cast<unsigned char>(pending_[offset + valid]);
                if (next < 0x80 || next > 0xbf ||
                    (valid == 1 && ((c == 0xe0 && next < 0xa0) || (c == 0xed && next > 0x9f) ||
                                   (c == 0xf0 && next < 0x90) || (c == 0xf4 && next > 0x8f)))) {
                    break;
                }
            }
            if (length && valid == length) {
                out.append(pending_, offset, length);
                offset += length;
            } else if (length && offset + valid == pending_.size() && !final) {
                break;
            } else {
                out += "\xef\xbf\xbd";
                offset += valid;
            }
        }
        pending_.erase(0, offset);
        return out;
    }
private:
    std::string pending_;
};

inline void require_utf8(const std::string & text) {
    Utf8Stream stream;
    if (stream.push(text, true) != text) {
        throw std::invalid_argument("text must be valid UTF-8");
    }
}

} // namespace mimir::detail
