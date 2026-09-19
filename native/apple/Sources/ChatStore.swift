import SwiftUI

@MainActor
final class ChatStore: ObservableObject {
    @Published var saved = SavedChats()
    @Published var selected: UUID?
    @Published var draft = ""
    @Published var streaming = ""
    @Published var pendingPrompt: String?
    @Published var loading = false
    @Published var generating = false
    @Published var ready = false
    @Published var notice: String?
    @Published var model: ModelAsset?
    @Published var showingSettings = false
    @Published var importer = false
    private let engine = MimirEngine()
    private var storage: ChatStorage?
    private var persistenceEnabled = true
    let contextTokens = 1024
    let replyTokens = 128
    var busy: Bool { loading || generating }
    var active: Conversation? { saved.conversations.first { $0.id == selected } }
    var messages: [ChatMessage] { active?.messages ?? [] }
    var modelMatches: Bool { active == nil || active?.modelID == model?.id }
    var canSend: Bool { ready && !busy && modelMatches && !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    var engineLabel: String {
        #if targetEnvironment(simulator)
        return "On-device · Simulator CPU"
        #else
        return "On-device · Metal"
        #endif
    }

    init(storage suppliedStorage: ChatStorage? = nil) {
        do {
            let storage = try suppliedStorage ?? ChatStorage()
            self.storage = storage
            saved = try storage.load()
            selected = saved.conversations.first?.id
        } catch {
            // Keep an unreadable archive intact. Never overwrite it with an empty default.
            persistenceEnabled = false
            notice = "Saved chats could not be opened. This session will not overwrite them. \(error.localizedDescription)"
        }
    }
    func start() {
        guard model == nil, !loading else { return }
        if let imported = saved.importedModel, let url = storage?.modelURL(imported),
           FileManager.default.fileExists(atPath: url.path) {
            load(imported)
        } else { useBundledModel() }
    }
    func useBundledModel() {
        guard !busy else { return }
        do {
            guard let url = Bundle.main.url(forResource: "Model", withExtension: "json") else {
                notice = "Import a Mimir GGUF model to start chatting."
                return
            }
            load(try JSONDecoder().decode(ModelAsset.self, from: Data(contentsOf: url)))
        } catch { notice = "The bundled model information could not be read." }
    }
    private func load(_ asset: ModelAsset) {
        guard !busy, let path = storage?.modelURL(asset)?.path else { return }
        loading = true
        ready = false
        #if targetEnvironment(simulator)
        let gpu = false
        #else
        let gpu = true
        #endif
        engine.loadModel(path, context: Int32(contextTokens), useGPU: gpu) { [weak self] error in
            guard let self else { return }
            self.loading = false
            if let error { self.notice = error; return }
            self.model = asset
            self.ready = true
            self.saved.importedModel = asset.bundled ? nil : asset
            self.persist()
        }
    }
    func importModel(_ url: URL) {
        guard !busy, let storage else { return }
        loading = true
        Task {
            do {
                let asset = try await Task.detached(priority: .userInitiated) { try storage.importModel(url) }.value
                loading = false
                load(asset)
            } catch {
                loading = false
                notice = "Could not import this model. \(error.localizedDescription)"
            }
        }
    }
    func select(_ id: UUID) {
        guard !busy else { return }
        selected = id
        draft = ""
        streaming = ""
    }
    func newChat() {
        guard !busy else { return }
        selected = nil
        draft = ""
        streaming = ""
    }
    func deleteActive() {
        guard !busy, let selected else { return }
        saved.conversations.removeAll { $0.id == selected }
        self.selected = nil
        persist()
    }
    func send() {
        guard canSend, let model else { return }
        let prompt = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        let history = messages.map { ["role": $0.role, "content": $0.content] }
        let previous = active
        draft = ""
        pendingPrompt = prompt
        streaming = ""
        generating = true
        notice = nil
        engine.reply(prompt, history: history, budget: Int32(replyTokens), onToken: { [weak self] token in
            self?.streaming += token
        }, completion: { [weak self] error, cancelled, limitReached in
            guard let self else { return }
            self.generating = false
            self.pendingPrompt = nil
            if let error {
                self.notice = error
                self.draft = prompt
            } else if cancelled {
                self.notice = "Reply stopped. Your message is back in the composer."
                self.draft = prompt
            } else {
                var chat = previous ?? Conversation(modelID: model.id)
                chat.messages += [ChatMessage(role: "user", content: prompt), ChatMessage(role: "assistant", content: self.streaming)]
                chat.title = String(chat.messages.first?.content.prefix(48) ?? "New chat")
                chat.updated = Date()
                self.saved.conversations.removeAll { $0.id == chat.id }
                self.saved.conversations.insert(chat, at: 0)
                self.selected = chat.id
                self.persist()
                if limitReached { self.notice = "Reply reached the 128-token limit. You can ask a follow-up." }
            }
            self.streaming = ""
        })
    }
    func stop() { if generating { engine.cancel() } }
    private func persist() {
        guard persistenceEnabled else {
            notice = "The saved archive could not be read. New chats are not being saved; the original archive is untouched."
            return
        }
        guard let storage else { return }
        do { try storage.save(saved) }
        catch { notice = "This chat could not be saved. \(error.localizedDescription)" }
    }
}
