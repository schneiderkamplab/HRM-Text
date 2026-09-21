import SwiftUI

// Bundle identifiers and storage paths deliberately remain stable across branding updates.
enum MimirBrand {
    static let name = "DFM Mimir"
    static let accent = Color(red: 0.72, green: 0.025, blue: 0.05)
}

struct MimirMark: View {
    var size: CGFloat = 40
    var body: some View {
        Image("MimirLogo")
            .resizable().scaledToFit()
            .frame(width: size, height: size)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.2))
            .accessibilityLabel("DFM Mimir logo")
    }
}

struct FoundationModelsLogo: View {
    var width: CGFloat = 200
    var body: some View {
        // Preserve the supplied red artwork on a legible surface in both appearances.
        Image("DFMLogo")
            .resizable().scaledToFit()
            .frame(width: width)
            .padding(12)
            .background(.white, in: RoundedRectangle(cornerRadius: 12))
            .accessibilityLabel("Danish Foundation Models")
    }
}
