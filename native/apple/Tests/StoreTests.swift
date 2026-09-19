import Foundation
import SwiftUI

// Test double for the asynchronous Objective-C bridge; compiled only in this test target.
@MainActor
final class MimirEngine {
    static var current: MimirEngine?
    var token: ((String) -> Void)?
    var completion: ((String?, Bool, Bool) -> Void)?
    var history: [[String: String]] = []
    var cancelled = false
    init() { Self.current = self }
    func loadModel(_ path: String, context: Int32, useGPU: Bool, completion: (String?) -> Void) { completion(nil) }
    func reply(_ prompt: String, history: [[String: String]], budget: Int32,
               onToken: @escaping (String) -> Void, completion: @escaping (String?, Bool, Bool) -> Void) {
        self.history = history; token = onToken; self.completion = completion
    }
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
        engine.completion?(nil, false, false)
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
        engine.completion?(nil, true, false)
        precondition(store.messages.count == 2 && store.draft == "Continue" && !store.generating)
        store.send()
        engine.completion?("Conversation full", false, false)
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
        engine.completion?(nil, true, false)
        precondition(store.selected == secondID && store.messages.isEmpty && store.draft == "New model")
        store.send()
        engine.completion?("Failure", false, false)
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
        engine.completion?(nil, false, false)
        precondition(store.selected == welcomeID && store.saved.conversations.count == 2)
        print("Store: immediate sidebar identity, first-turn stop/error, empty-chat reload/delete, welcome send; complete-turn persistence, prompt restore, stop/error rollback and model identity isolation passed")
    }
}
