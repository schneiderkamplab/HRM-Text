import Foundation

struct GenerationSettings: Codable, Equatable {
    var contextTokens: Int
    var replyTokens: Int

    static func defaults(context: Int) -> Self {
        Self(contextTokens: context, replyTokens: max(512, min(2048, context / 4)))
    }
    var validationError: String? {
        guard contextTokens >= 1024, contextTokens <= Int(Int32.max) else {
            return "Context must be at least 1,024 tokens and fit the runtime's token range."
        }
        guard replyTokens >= 1, replyTokens <= contextTokens - 256 else {
            return "Reply budget must be positive and leave at least 256 tokens for the prompt."
        }
        return nil
    }
}
