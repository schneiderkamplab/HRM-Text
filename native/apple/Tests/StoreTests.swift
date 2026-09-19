import Foundation
import SwiftUI

// Test double for the asynchronous Objective-C bridge; compiled only in this test target.
@MainActor
final class MimirEngine {
    static var current: MimirEngine?
    var token: ((String) -> Void)?
    var completion: ((String?, Bool, Bool, [String: Any]?) -> Void)?
    var history: [[String: String]] = []
    var cancelled = false
    var loadError: String?
    var loadedContext: Int32?
    var replyBudget: Int32?
    var replyMemory: [String: Any]?
    var autoCompact = true
    var onSummary: ((String, Int32) -> Void)?
    var onPrepared: ((Int32) -> Void)?
    func countContext(_ history: [[String: String]], memory: [String: Any]?, completion: (Int32) -> Void) { completion(42) }
    var onCompacting: (() -> Void)?
    init() { Self.current = self }
    func loadModel(_ path: String, context: Int32, useGPU: Bool, profile: [String: Any], completion: (String?, Int32, Int32) -> Void) { loadedContext = context; completion(loadError, context == 0 ? 4096 : context, 4096) }
    func reply(_ prompt: String, history: [[String: String]], memory: [String: Any]?, autoCompact: Bool, budget: Int32, onCompacting: @escaping () -> Void, onSummary: @escaping (String, Int32) -> Void, onPrepared: @escaping (Int32) -> Void,
               onToken: @escaping (String) -> Void, completion: @escaping (String?, Bool, Bool, [String: Any]?) -> Void) {
        self.onSummary = onSummary; self.onPrepared = onPrepared; self.replyMemory = memory; self.autoCompact = autoCompact; self.onCompacting = onCompacting
        self.replyBudget = budget; self.history = history; token = onToken; self.completion = completion
    }
    var shutdownCompletion: (() -> Void)?
    func shutdown(completion: @escaping () -> Void) { cancelled = true; shutdownCompletion = completion }
    func cancel() { cancelled = true }
}
@main
struct StoreTests {
    @MainActor static func main() throws {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temp) }
        let storage = try ChatStorage(directory: temp)
        let store = ChatStore(storage: storage)
        store.newChat()
        let initialID = store.selected!
        precondition(store.active?.title == "New chat" && store.active?.modelID == nil)
        let initialArchive = try storage.load()
        precondition(initialArchive.conversations.first?.id == initialID)
        store.model = ModelAsset(id: "mimir", name: "test", filename: "test.gguf", bundled: false)
        store.ready = true
        let engine = MimirEngine.current!
        store.draft = "Hej"
        store.send()
        precondition(store.generating && !store.canSend && store.saved.conversations.count == 1)
        precondition(store.selected == initialID && store.active?.title == "Hej" && store.messages.isEmpty)
        precondition(store.active?.modelID == "mimir")
        let pendingArchive = try storage.load()
        precondition(pendingArchive.conversations[0].messages.isEmpty)
        store.newChat()
        precondition(store.selected == initialID && store.saved.conversations.count == 1)
        engine.token?("Hejsa")
        engine.completion?(nil, false, false, nil)
        precondition(store.messages.count == 2 && store.messages.last?.content == "Hejsa")
        precondition(store.selected == initialID && store.saved.conversations.count == 1)
        let archive = try storage.load()
        precondition(archive.conversations[0].messages == store.messages)
        store.draft = "Continue"
        store.send()
        precondition(engine.history.count == 2)
        engine.token?("partial")
        store.stop()
        precondition(engine.cancelled)
        engine.completion?(nil, true, false, nil)
        precondition(store.messages.count == 2 && store.draft == "Continue" && !store.generating)
        store.send()
        engine.completion?("Conversation full", false, false, nil)
        precondition(store.messages.count == 2 && store.draft == "Continue" && store.notice == "Conversation full")
        store.model = ModelAsset(id: "different", name: "test", filename: "other.gguf", bundled: false)
        precondition(!store.canSend)
        store.newChat()
        store.draft = "New model"
        precondition(store.canSend)
        let secondID = store.selected!
        precondition(secondID != initialID && store.saved.conversations.count == 2)
        store.send()
        engine.token?("partial")
        store.stop()
        engine.completion?(nil, true, false, nil)
        precondition(store.selected == secondID && store.messages.isEmpty && store.draft == "New model")
        store.send()
        engine.completion?("Failure", false, false, nil)
        precondition(store.selected == secondID && store.saved.conversations.count == 2 && store.messages.isEmpty)
        let restored = ChatStore(storage: storage)
        precondition(restored.active?.id == secondID && restored.messages.isEmpty)
        store.deleteActive()
        precondition(store.saved.conversations.count == 1)
        // Sending from the initial welcome state also inserts before any callback.
        store.draft = "From welcome"
        store.send()
        let welcomeID = store.selected!
        precondition(welcomeID != initialID && store.active?.title == "From welcome")
        engine.token?("Hello")
        engine.completion?(nil, false, false, nil)
        precondition(store.selected == welcomeID && store.saved.conversations.count == 2)
        let originalMessages = store.messages
        store.draft = "Compact this conversation"
        store.send()
        engine.onCompacting?()
        precondition(store.compacting && store.activityLabel == "DFM Mimir is compacting…")
        engine.onSummary?("Partial", 2)
        precondition(store.summaryPreview?.summary == "Partial" && store.summaryPreview?.position == originalMessages.count)
        precondition(store.visibleSummary == nil)
        engine.onSummary?("Complete summary", 2)
        precondition(store.summaryPreview?.summary == "Complete summary")
        engine.onPrepared?(123)
        precondition(!store.compacting && store.usedContext == 123 && store.activityLabel == "DFM Mimir is thinking…")
        engine.token?("After summary")
        precondition(!store.compacting)
        engine.completion?(nil, false, false, ["summary": "Earlier greeting", "covered": 2])
        precondition(Array(store.messages.prefix(2)) == originalMessages && store.active?.memory?.covered == 2)
        precondition(store.usedContext == 42 && store.summaryPreview == nil)
        let compactedArchive = try storage.load()
        precondition(compactedArchive.conversations.first?.memory?.summary == "Earlier greeting" && compactedArchive.conversations.first?.memory?.position == originalMessages.count)
        store.setCompaction(showSummary: true)
        store.draft = "Stop compaction"
        store.send()
        precondition(engine.replyMemory?["covered"] as? Int == 2)
        engine.onCompacting?()
        engine.onSummary?("Discard me", 2)
        precondition(store.visibleSummary?.summary == "Discard me" && store.summaryPosition == store.messages.count)
        store.stop()
        engine.completion?(nil, true, false, ["summary": "Must not persist", "covered": 4])
        precondition(store.active?.memory?.summary == "Earlier greeting" && !store.compacting)
        precondition(store.summaryPreview == nil)
        store.setCompaction(enabled: false, showSummary: true)
        precondition(store.visibleSummary?.summary == "Earlier greeting" && store.summaryPosition == originalMessages.count)
        store.send()
        precondition(!engine.autoCompact && engine.history.count == store.messages.count)
        engine.completion?("Capacity", false, false, nil)
        precondition(store.active?.memory?.summary == "Earlier greeting")
        let savedPreferences = ChatStore(storage: storage)
        precondition(!savedPreferences.compactionSettings.enabled && savedPreferences.compactionSettings.showSummary)
        store.setCompaction(enabled: true, showSummary: false)
        precondition(store.contextTokens == 1024 && store.replyTokens == 512)
        let completed = store.messages
        let custom = GenerationSettings(contextTokens: 8192, replyTokens: 512)
        store.applySettings(custom)
        precondition(engine.loadedContext == 8192 && store.generationSettings == custom && store.messages == completed)
        let savedSettings = try storage.load()
        precondition(savedSettings.generationSettings == custom)
        let reloadedSettings = ChatStore(storage: storage)
        precondition(reloadedSettings.generationSettings == custom)
        engine.loadError = "Not enough memory"
        store.applySettings(GenerationSettings(contextTokens: 16384, replyTokens: 2048))
        precondition(!store.ready && store.generationSettings == custom && store.notice == "Not enough memory")
        engine.loadError = nil
        store.applySettings(custom)
        precondition(store.ready && store.messages == completed)
        store.draft = "Budget check"
        store.send()
        precondition(engine.replyBudget == 512)
        engine.token?("limited")
        engine.completion?(nil, false, true, nil)
        precondition(store.notice?.contains("512-token") == true)
        store.useMemoryDefaults()
        precondition(store.saved.generationSettings == nil && store.contextTokens == 4096)
        for invalid in [GenerationSettings(contextTokens: 512, replyTokens: 128),
                        GenerationSettings(contextTokens: 1024, replyTokens: 1024),
                        GenerationSettings(contextTokens: Int.max, replyTokens: 512)] {
            precondition(invalid.validationError != nil)
            store.applySettings(invalid)
            precondition(store.contextTokens == 4096)
        }
        precondition(GenerationSettings(contextTokens: 32768, replyTokens: 512).validationError == nil)
        precondition(GenerationSettings(contextTokens: 32769, replyTokens: 512).validationError != nil)
        var next = ModelProfile()
        next.name = "Future Mimir fixture"
        next.maximumContext = 65536
        next.contextTiers.append(65536)
        next.memoryBytesPerToken = 524288
        next.maximumDefaultReply = 4096
        precondition(next.validationError == nil)
        precondition(next.defaults(context: 65536).replyTokens == 4096)
        precondition(GenerationSettings(contextTokens: 65536, replyTokens: 4096).validationError(profile: next) == nil)
        let profileURL = temp.appendingPathComponent("profile.json")
        try JSONEncoder().encode(next).write(to: profileURL)
        store.importProfile(profileURL)
        precondition(store.profile == next && store.trainingContext == 4096)
        let profileSaved = try storage.load()
        precondition(profileSaved.importedModel?.profile == next)
        let profileReload = ChatStore(storage: storage)
        try FileManager.default.createDirectory(at: temp.appendingPathComponent("Models"), withIntermediateDirectories: true)
        try Data().write(to: temp.appendingPathComponent("Models").appendingPathComponent(profileSaved.importedModel!.filename))
        profileReload.start()
        precondition(profileReload.profile == next && profileReload.ready)
        let example = try JSONDecoder().decode(ModelProfile.self, from: Data(contentsOf: URL(fileURLWithPath: "native/apple/Resources/DFM-Mimir-v1.profile.json")))
        precondition(example == ModelProfile())
        next.contextTiers = [65536, 1024]
        precondition(next.validationError != nil)
        var shutdownDone = false
        profileReload.shutdown { shutdownDone = true }
        precondition(profileReload.busy && !profileReload.canSend && !shutdownDone)
        MimirEngine.current!.shutdownCompletion?()
        precondition(shutdownDone)
        print("Profiles: 32768 context, future-model policy, JSON import, persistence and invalid policy passed")
        print("Settings: custom persistence, reload/failure/recovery, budget forwarding, automatic defaults and validation passed")
        print("Store: immediate sidebar identity, first-turn stop/error, empty-chat reload/delete, welcome send; complete-turn persistence, prompt restore, stop/error rollback and model identity isolation passed")
    }
}
