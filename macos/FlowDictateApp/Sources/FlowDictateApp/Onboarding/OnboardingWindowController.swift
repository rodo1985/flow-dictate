import AppKit
import SwiftUI

@MainActor
final class OnboardingWindowController: NSObject, NSWindowDelegate {
    private var window: NSWindow?

    func show(appState: AppState) {
        if let existingWindow = window {
            NSApp.activate(ignoringOtherApps: true)
            existingWindow.makeKeyAndOrderFront(nil)
            return
        }

        let onboardingWindow = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 560, height: 360),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        onboardingWindow.title = "Flow Dictate Setup"
        onboardingWindow.isReleasedWhenClosed = false
        onboardingWindow.delegate = self
        onboardingWindow.center()
        onboardingWindow.contentView = NSHostingView(rootView: OnboardingView(appState: appState))

        window = onboardingWindow
        NSApp.activate(ignoringOtherApps: true)
        onboardingWindow.makeKeyAndOrderFront(nil)
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
