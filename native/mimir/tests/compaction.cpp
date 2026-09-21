#include "mimir/compaction.h"
#include "../utf8.h"
#include <iostream>
#include <stdexcept>
#include <string>
using namespace mimir;
void require(bool condition, const char * message) { if (!condition) throw std::runtime_error(message); }
struct Codec {
    Prompt prepare(const std::vector<Message> & messages) const {
        size_t size = 8;
        for (const auto & m : messages) size += m.content.size() + 8;
        return {"", std::vector<llama_token>(size)};
    }
};
struct Model {
    Codec codec;
    std::string system, output = "Brief useful notes.";
    size_t context = 1024;
    std::vector<std::string> calls;
    bool * stop = nullptr;
    bool fail = false;
    void restore_history(const std::vector<Message> &) {}
    Reply reply(const std::string & input, uint32_t budget, const std::function<void(const std::string &)> & stream) {
        std::vector<Message> messages;
        if (!system.empty()) messages.push_back({"system", system});
        messages.push_back({"user", input});
        require(codec.prepare(messages).tokens.size() + budget <= context, "unbounded summary request");
        calls.push_back(input);
        stream(output);
        if (stop) *stop = true;
        Reply result;
        result.text = output;
        if (fail) result.status = Status::capacity;
        return result;
    }
};
int main() {
    try {
        Codec codec;
        Model model;
        bool stopped = false;
        int notifications = 0, promptUpdates = 0;
        const auto run = [&](const std::vector<Message> & history, const std::string & prompt,
                             size_t reply = 128, compaction::Memory memory = {}) {
            return compaction::compact(model, codec, model.system, history, memory, prompt,
                model.context, reply, [&]{return stopped;}, [&]{++notifications;},
                [](const compaction::Memory & m){require(m.covered % 2 == 0, "partial turn coverage");},
                [&](const std::string &){++promptUpdates;});
        };
        auto shortReply = run({}, "Hello");
        require(model.calls.empty() && shortReply.prompt == "Hello", "short prompt changed");
        std::string huge;
        for (int i=0;i<1000;++i) huge += "Dansk æøå 😀 tekst\n";
        auto shortened = run({}, huge, 512);
        require(shortened.prompt.find(model.output) != std::string::npos && model.calls.size() > 1 && promptUpdates > 1, "oversized prompt not chunked");
        std::string source;
        for (const auto & input : model.calls) {
            const std::string marker = "\nSource (continued in order):\n";
            source += input.substr(input.find(marker) + marker.size());
        }
        require(source == huge, "chunking lost or duplicated source bytes");
        require(notifications == 1, "compacting notification repeated");
        // Validate UTF-8 at chunk edges, including multi-byte emoji and Danish text.
        for (const auto & input : model.calls) {
            mimir::detail::require_utf8(input);
        }
        model.calls.clear();
        std::vector<Message> full = {{"user", huge}, {"assistant", "Original answer"},
            {"user", "Recent"}, {"assistant", "Keep"}};
        auto remembered = run(full, "Next");
        require(remembered.memory.covered == 2 && model.calls.size() > 1, "oversized old turn not chunked");
        require(full[0].content == huge && remembered.messages.back().content == "Keep", "original or recent turn changed");
        model.calls.clear();
        std::vector<Message> turns;
        for (int i=0;i<12;++i) {
            turns.push_back({"user", "Turn " + std::to_string(i) + ": " + std::string(48,'x')});
            turns.push_back({"assistant", std::string(35,'y')});
        }
        auto packed = run(turns, "Next");
        require(packed.memory.covered > 2, "only one turn compacted");
        require(model.calls.front().find("Turn 1:") != std::string::npos, "whole turns not packed");
        auto effective = packed.messages; effective.push_back({"user", packed.prompt});
        require(codec.prepare(effective).tokens.size() + 128 <= 768, "headroom target not reached");
        model.calls.clear();
        model.output = std::string(128, 'n');
        const std::vector<Message> tiny = {{"user", "Hi"}, {"assistant", "OK"}};
        const std::string almostFull(810, 'p');
        auto noGain = run(tiny, almostFull);
        require(noGain.memory.covered == 0 && noGain.prompt == almostFull, "optional compaction expanded a fitting request");
        model.output = "Brief useful notes.";
        model.calls.clear();
        stopped = true;
        auto cancelled = run(full, "Next", 128, {"Saved notes", 2});
        require(cancelled.cancelled && cancelled.memory.summary == "Saved notes" && model.calls.empty(), "early cancellation lost saved memory");
        stopped = false; model.stop = &stopped;
        cancelled = run(full, huge);
        require(cancelled.cancelled && cancelled.memory.covered == 0 && cancelled.prompt == huge, "mid-compaction committed partial state");
        stopped = false; model.stop = nullptr;
        for (int mode=0;mode<3;++mode) {
            model.output = mode == 0 ? " " : "Notes";
            model.fail = mode == 1;
            model.system = mode == 2 ? std::string(950,'s') : "";
            bool rejected = false;
            try { run({}, huge); } catch (const std::runtime_error &) { rejected = true; }
            require(rejected, "empty/error/oversized system accepted");
        }
        model.system.clear(); model.fail = false; model.output = "Notes";
        // Reply reservation is checked even when input alone would fit.
        require(run({}, std::string(600,'p'), 512).prompt.size() < 496, "reply reservation ignored");
        std::cout << "PASS: bounded prompt/history chunks, exact source coverage, UTF-8, turn packing, headroom, cancellation, errors and reply reserve\n";
    } catch (const std::exception & e) { std::cerr << e.what() << '\n'; return 1; }
}
