import AppKit
import SwiftUI

@MainActor
final class SettingsWindowController: NSObject, NSWindowDelegate {
    private var window: NSWindow?

    func show(appState: AppState) {
        if let existingWindow = window {
            NSApp.activate(ignoringOtherApps: true)
            existingWindow.makeKeyAndOrderFront(nil)
            return
        }

        let settingsWindow = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 420),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        settingsWindow.title = "Flow Dictate Settings"
        settingsWindow.isReleasedWhenClosed = false
        settingsWindow.delegate = self
        settingsWindow.center()
        settingsWindow.contentView = NSHostingView(rootView: SettingsView(appState: appState))

        window = settingsWindow
        NSApp.activate(ignoringOtherApps: true)
        settingsWindow.makeKeyAndOrderFront(nil)
    }

    func close() {
        guard let existingWindow = window else {
            return
        }
        existingWindow.orderOut(nil)
        existingWindow.close()
        window = nil
    }

    func windowWillClose(_ notification: Notification) {
        window = nil
    }
}
