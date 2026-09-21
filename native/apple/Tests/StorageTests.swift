import Foundation

@main
struct StorageTests {
    static func main() throws {
        let temp = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer { try? FileManager.default.removeItem(at: temp) }
        let store = try ChatStorage(directory: temp)
        let empty = try store.load()
        precondition(empty.conversations.isEmpty)
        var chat = Conversation(modelID: "test")
        chat.messages = [ChatMessage(role: "user", content: "Hej æøå 👋"), ChatMessage(role: "assistant", content: "Hej!")]
        var saved = SavedChats(conversations: [chat])
        try store.save(saved)
        let reloaded = try store.load()
        precondition(reloaded.conversations[0].messages == chat.messages)
        saved.conversations[0].messages.removeLast()
        try store.save(saved)
        do { _ = try store.load(); fatalError("accepted incomplete transcript") }
        catch is CocoaError { }
        let source = temp.appendingPathComponent("model.gguf")
        try Data("GGUFfake test bytes".utf8).write(to: source)
        let imported = try store.importModel(source)
        precondition(imported.id.count == 64)
        let copied = try Data(contentsOf: store.modelURL(imported)!)
        let original = try Data(contentsOf: source)
        precondition(copied == original)
        let repeated = try store.importModel(source)
        precondition(repeated.id == imported.id)
        precondition(store.modelURL(ModelAsset(id: "x", name: "bad", filename: "../escape.gguf", bundled: false)) == nil)
        try Data("invalid".utf8).write(to: source)
        do { _ = try store.importModel(source); fatalError("accepted invalid GGUF") }
        catch is CocoaError { }
        print("Storage: Unicode round-trip, invalid history, model import/hash/deduplication and path validation passed")
    }
}
