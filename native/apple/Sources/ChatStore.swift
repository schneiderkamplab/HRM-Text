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
    @Published private(set) var shuttingDown = false
    @Published private(set) var generationSettings = ModelProfile().defaults(context: ModelProfile().minimumContext)
    @Published private(set) var trainingContext: Int?
    var profile: ModelProfile { model?.profile ?? ModelProfile() }
    var contextTokens: Int { generationSettings.contextTokens }
    var replyTokens: Int { generationSettings.replyTokens }
    var busy: Bool { shuttingDown || loading || generating }
    var active: Conversation? { saved.conversations.first { $0.id == selected } }
    var messages: [ChatMessage] { active?.messages ?? [] }
    var modelMatches: Bool { messages.isEmpty || active?.modelID == model?.id }
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
            if let settings = saved.generationSettings, settings.validationError(profile: saved.importedModel?.profile ?? ModelProfile()) == nil {
                generationSettings = settings
            }
            selected = saved.conversations.first?.id
        } catch {
            // Keep an unreadable archive intact. Never overwrite it with an empty default.
            persistenceEnabled = false
            notice = "Saved chats could not be opened. This session will not overwrite them. \(error.localizedDescription)"
        }
    }
    func shutdown(completion: @escaping () -> Void) {
        shuttingDown = true
        ready = false
        engine.shutdown(completion: completion)
    }
    func start() {
        guard model == nil, !busy else { return }
        if let imported = saved.importedModel, !imported.bundled, let url = storage?.modelURL(imported),
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
            var asset = try JSONDecoder().decode(ModelAsset.self, from: Data(contentsOf: url))
            // A new app bundle may contain different weights: never reuse the old identity.
            if model == nil, let previous = saved.importedModel, previous.id == asset.id {
                asset.profile = previous.profile ?? asset.profile
            }
            load(asset)
        } catch { notice = "The bundled model information could not be read." }
    }
    func useMemoryDefaults() {
        applySettings(profile.defaults(context: profile.minimumContext), automatic: true)
    }
    func applySettings(_ settings: GenerationSettings, automatic: Bool = false) {
        guard !busy else { return }
        if let error = settings.validationError(profile: profile) { notice = error; return }
        if let model, automatic || settings.contextTokens != contextTokens || !ready {
            load(model, settings: settings, automatic: automatic)
        } else {
            generationSettings = settings
            saved.generationSettings = automatic ? nil : settings
            persist()
        }
    }
    private func load(_ asset: ModelAsset, settings requested: GenerationSettings? = nil, automatic: Bool = false) {
        guard !busy, let path = storage?.modelURL(asset)?.path else { return }
        let policy = asset.profile ?? ModelProfile()
        if let error = policy.validationError { notice = error; return }
        let settings = requested ?? generationSettings
        let switchingModel = saved.importedModel.map { $0.id != asset.id } ?? false
        let chooseAutomatically = automatic || (requested == nil && (saved.generationSettings == nil || switchingModel))
        if !chooseAutomatically, let error = settings.validationError(profile: policy) { notice = error; return }
        model = asset
        loading = true
        ready = false
        #if targetEnvironment(simulator)
        let gpu = false
        #else
        let gpu = true
        #endif
        engine.loadModel(path, context: chooseAutomatically ? 0 : Int32(settings.contextTokens), useGPU: gpu, profile: policy.nativeOptions) { [weak self] error, loadedContext, trainedContext in
            guard let self else { return }
            self.loading = false
            if let error { self.notice = error; return }
            self.model = asset
            self.trainingContext = Int(trainedContext)
            self.notice = nil
            self.generationSettings = chooseAutomatically
                ? policy.defaults(context: Int(loadedContext)) : settings
            if requested != nil || switchingModel { self.saved.generationSettings = chooseAutomatically ? nil : settings }
            self.ready = true
            self.saved.importedModel = asset
            self.persist()
        }
    }
    func importProfile(_ url: URL) {
        guard !busy, var asset = model else { notice = "Load a model before selecting its profile."; return }
        let access = url.startAccessingSecurityScopedResource()
        defer { if access { url.stopAccessingSecurityScopedResource() } }
        do {
            let policy = try JSONDecoder().decode(ModelProfile.self, from: Data(contentsOf: url))
            if let error = policy.validationError { notice = error; return }
            asset.profile = policy
            load(asset, settings: policy.defaults(context: policy.minimumContext), automatic: true)
        } catch { notice = "Could not read model profile. \(error.localizedDescription)" }
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
        draft = ""
        streaming = ""
        saveConversation(Conversation(modelID: model?.id))
    }
    private func saveConversation(_ chat: Conversation) {
        saved.conversations.removeAll { $0.id == chat.id }
        saved.conversations.insert(chat, at: 0)
        selected = chat.id
        persist()
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
        var conversation = active ?? Conversation(modelID: model.id)
        if conversation.messages.isEmpty {
            conversation.modelID = model.id
            conversation.title = String(prompt.prefix(48))
        }
        conversation.updated = Date()
        let previous = conversation
        notice = nil
        saveConversation(conversation)
        draft = ""
        pendingPrompt = prompt
        streaming = ""
        generating = true
        let budget = replyTokens
        engine.reply(prompt, history: history, budget: Int32(budget), onToken: { [weak self] token in
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
                var chat = previous
                chat.messages += [ChatMessage(role: "user", content: prompt), ChatMessage(role: "assistant", content: self.streaming)]
                chat.title = String(chat.messages.first?.content.prefix(48) ?? "New chat")
                chat.updated = Date()
                self.saveConversation(chat)
                if limitReached { self.notice = "Reply reached the \(budget)-token limit. You can increase the reply budget in settings." }
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
