import Foundation

struct GenerationSettings: Codable, Equatable {
    var contextTokens: Int
    var replyTokens: Int

    static func defaults(context: Int) -> Self { ModelProfile().defaults(context: context) }
    var validationError: String? { validationError(profile: ModelProfile()) }
    func validationError(profile: ModelProfile) -> String? {
        guard contextTokens >= profile.minimumContext, contextTokens <= profile.maximumContext else {
            return "Context must be between \(profile.minimumContext) and \(profile.maximumContext) tokens."
        }
        guard replyTokens >= 1, replyTokens <= contextTokens - profile.promptReserve else {
            return "Reply budget must be positive and leave at least \(profile.promptReserve) tokens for the prompt."
        }
        return nil
    }
}
