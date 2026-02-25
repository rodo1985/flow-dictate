import AppKit
import SwiftUI

@MainActor
final class HUDWindowController {
    private var panel: NSPanel?
    private var hideTask: Task<Void, Never>?
    private(set) var isVisible: Bool = false

    func show(state: HUDState) {
        let panel = ensurePanel()
        panel.contentView = NSHostingView(rootView: HUDIndicatorView(state: state))
        position(panel: panel)

        if !panel.isVisible {
            panel.orderFrontRegardless()
        }
        isVisible = true

        scheduleAutoHideIfNeeded(for: state)
    }

    func hide() {
        hideTask?.cancel()
        hideTask = nil
        panel?.orderOut(nil)
        isVisible = false
    }

    private func scheduleAutoHideIfNeeded(for state: HUDState) {
        hideTask?.cancel()
        hideTask = nil

        let delaySeconds: Double
        switch state {
        case .success:
            delaySeconds = 1.2
        case .error:
            delaySeconds = 3.0
        case .recording, .transcribing:
            return
        }

        hideTask = Task {
            try? await Task.sleep(for: .seconds(delaySeconds))
            await MainActor.run {
                self.hide()
            }
        }
    }

    private func ensurePanel() -> NSPanel {
        if let existingPanel = panel {
            return existingPanel
        }

        let nextPanel = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: 88, height: 88),
            styleMask: [.borderless, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )
        nextPanel.level = .statusBar
        nextPanel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        nextPanel.backgroundColor = .clear
        nextPanel.isOpaque = false
        nextPanel.hasShadow = false
        nextPanel.ignoresMouseEvents = true
        nextPanel.hidesOnDeactivate = false

        panel = nextPanel
        return nextPanel
    }

    private func position(panel: NSPanel) {
        guard let screen = NSScreen.main else {
            return
        }

        let visibleFrame = screen.visibleFrame
        let panelSize = panel.frame.size
        let topMargin: CGFloat = 42
        let originX = visibleFrame.midX - (panelSize.width / 2)
        let originY = visibleFrame.maxY - panelSize.height - topMargin
        panel.setFrameOrigin(NSPoint(x: originX, y: originY))
    }
}
