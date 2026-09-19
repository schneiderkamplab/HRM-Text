import Foundation
import CryptoKit

struct ChatMessage: Codable, Identifiable, Equatable {
    var id = UUID()
    let role: String
    var content: String
}
struct Conversation: Codable, Identifiable {
    var id = UUID()
    var title = "New chat"
    var updated = Date()
    var messages: [ChatMessage] = []
    let modelID: String
}
struct ModelAsset: Codable, Equatable {
    let id: String
    let name: String
    let filename: String
    var bundled: Bool
}
struct SavedChats: Codable {
    var version = 1
    var conversations: [Conversation] = []
    var importedModel: ModelAsset?
}

struct ChatStorage {
    let directory: URL
    init(directory: URL? = nil) throws {
        self.directory = try directory ?? FileManager.default.url(for: .applicationSupportDirectory,
            in: .userDomainMask, appropriateFor: nil, create: true).appendingPathComponent("MimirChat", isDirectory: true)
        try FileManager.default.createDirectory(at: self.directory, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        var localDirectory = self.directory
        try localDirectory.setResourceValues(values)
    }
    func load() throws -> SavedChats {
        let file = directory.appendingPathComponent("conversations.json")
        guard FileManager.default.fileExists(atPath: file.path) else { return SavedChats() }
        let data = try JSONDecoder().decode(SavedChats.self, from: Data(contentsOf: file))
        guard data.version == 1,
              Set(data.conversations.map(\.id)).count == data.conversations.count,
              data.conversations.allSatisfy({ chat in
                  chat.messages.count % 2 == 0 && chat.messages.enumerated().allSatisfy {
                      $0.element.role == ($0.offset % 2 == 0 ? "user" : "assistant")
                  }
              }) else { throw CocoaError(.fileReadCorruptFile) }
        return data
    }
    func save(_ state: SavedChats) throws {
        try JSONEncoder().encode(state).write(to: directory.appendingPathComponent("conversations.json"), options: .atomic)
    }
    func modelURL(_ asset: ModelAsset) -> URL? {
        if asset.bundled { return Bundle.main.url(forResource: "Mimir", withExtension: "gguf") }
        guard asset.filename == URL(fileURLWithPath: asset.filename).lastPathComponent else { return nil }
        return directory.appendingPathComponent("Models").appendingPathComponent(asset.filename)
    }
    func importModel(_ source: URL) throws -> ModelAsset {
        let access = source.startAccessingSecurityScopedResource()
        defer { if access { source.stopAccessingSecurityScopedResource() } }
        guard source.pathExtension.lowercased() == "gguf" else { throw CocoaError(.fileReadUnsupportedScheme) }
        let folder = directory.appendingPathComponent("Models", isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let staging = folder.appendingPathComponent(UUID().uuidString + ".partial")
        defer { try? FileManager.default.removeItem(at: staging) }
        try FileManager.default.copyItem(at: source, to: staging)
        let handle = try FileHandle(forReadingFrom: staging)
        defer { try? handle.close() }
        guard try handle.read(upToCount: 4) == Data("GGUF".utf8) else { throw CocoaError(.fileReadCorruptFile) }
        try handle.seek(toOffset: 0)
        var hash = SHA256()
        while let chunk = try handle.read(upToCount: 1 << 20), !chunk.isEmpty { hash.update(data: chunk) }
        let id = hash.finalize().map { String(format: "%02x", $0) }.joined()
        let filename = id + ".gguf"
        let destination = folder.appendingPathComponent(filename)
        if !FileManager.default.fileExists(atPath: destination.path) {
            try FileManager.default.moveItem(at: staging, to: destination)
        }
        return ModelAsset(id: id, name: source.deletingPathExtension().lastPathComponent, filename: filename, bundled: false)
    }
}
