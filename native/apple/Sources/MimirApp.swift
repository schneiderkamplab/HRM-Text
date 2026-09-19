import SwiftUI

@main
struct MimirApp: App {
    @StateObject private var store = ChatStore()
    var body: some Scene {
        WindowGroup {
            ContentView(store: store)
                .tint(MimirBrand.accent)
                .task { store.start() }
                #if os(macOS)
                .frame(minWidth: 760, minHeight: 580)
                #endif
        }
        #if os(macOS)
        .defaultSize(width: 1060, height: 760)
        #endif
    }
}
