import Foundation

/// Versioned deployment policy; GGUF remains authoritative for weights, template and training context.
struct ModelProfile: Codable, Equatable {
    var version = 1
    var name = "DFM Mimir v1"
    var minimumContext = 1024
    var maximumContext = 32768
    var contextTiers = [1024, 2048, 4096, 8192, 16384, 32768]
    var minimumReply = 512
    var maximumDefaultReply = 2048
    var replyContextDivisor = 4
    var promptReserve = 256
    var memoryFraction = 0.70
    var fixedMemoryBytes: UInt64 = 256 * 1024 * 1024
    var memoryBytesPerToken: UInt64 = 2 * 1024 * 1024
    var cpuAttentionBytesPerTokenSquared: UInt64 = 96
    var threads = 4
    var systemPrompt = "You are Mimir, a local assistant powered by DFM-Mimir from Danish Foundation Models. Your model was developed by Danish Foundation Models, not OpenAI. You run on the user's device. Answer in the user's language."

    var validationError: String? {
        guard version == 1, !name.isEmpty,
              minimumContext >= 1, maximumContext <= Int(Int32.max), maximumContext >= minimumContext,
              promptReserve >= 1, promptReserve < minimumContext,
              minimumReply >= 1, minimumReply <= minimumContext - promptReserve,
              maximumDefaultReply >= minimumReply, maximumDefaultReply <= maximumContext - promptReserve,
              replyContextDivisor >= 1,
              !contextTiers.isEmpty, contextTiers == Array(Set(contextTiers)).sorted(),
              contextTiers.first == minimumContext, contextTiers.last == maximumContext,
              memoryFraction.isFinite, memoryFraction > 0, memoryFraction <= 1,
              memoryBytesPerToken > 0, threads >= 1, threads <= 256 else {
            return "Invalid model profile: check its version, context/reply bounds and memory policy."
        }
        return nil
    }
    func defaults(context: Int) -> GenerationSettings {
        GenerationSettings(contextTokens: context, replyTokens:
            min(context - promptReserve, max(minimumReply, min(maximumDefaultReply, context / replyContextDivisor))))
    }
    var nativeOptions: [String: Any] {
        ["minimumContext": minimumContext, "maximumContext": maximumContext,
         "contextTiers": contextTiers, "memoryFraction": memoryFraction,
         "fixedMemoryBytes": fixedMemoryBytes, "memoryBytesPerToken": memoryBytesPerToken,
         "cpuAttentionBytesPerTokenSquared": cpuAttentionBytesPerTokenSquared,
         "threads": threads, "systemPrompt": systemPrompt]
    }
}
