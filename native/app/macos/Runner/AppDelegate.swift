import Cocoa
import FlutterMacOS

@main
class AppDelegate: FlutterAppDelegate {
  override func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
    // Keep the local API and retained Flutter window available until explicit Quit.
    return false
  }

  @IBAction func showMainWindow(_ sender: Any?) {
    guard let window = mainFlutterWindow else { return }
    if window.isMiniaturized {
      window.deminiaturize(sender)
    }
    window.makeKeyAndOrderFront(sender)
    NSApp.activate(ignoringOtherApps: true)
  }

  override func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
    showMainWindow(sender)
    return true
  }

  override func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool {
    return true
  }
}
