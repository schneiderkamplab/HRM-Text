import SwiftUI

@main
struct MimirApp: App {
    @StateObject private var store = ChatStore()
    #if os(macOS)
    @NSApplicationDelegateAdaptor(MimirAppDelegate.self) private var appDelegate
    #endif
    var body: some Scene {
        WindowGroup {
            ContentView(store: store)
                .tint(MimirBrand.accent)
                .task {
                    #if os(macOS)
                    appDelegate.store = store
                    #endif
                    store.start()
                }
                #if os(macOS)
                .frame(minWidth: 760, minHeight: 580)
                #endif
        }
        #if os(macOS)
        .defaultSize(width: 1060, height: 760)
        #endif
    }
}

#if os(macOS)
@MainActor
final class MimirAppDelegate: NSObject, NSApplicationDelegate {
    var store: ChatStore?
    private var terminating = false

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let store else { return .terminateNow }
        if !terminating {
            terminating = true
            store.shutdown { sender.reply(toApplicationShouldTerminate: true) }
        }
        // Keep the main run loop alive for inference completion and resource teardown.
        return .terminateLater
    }
}
#endif
