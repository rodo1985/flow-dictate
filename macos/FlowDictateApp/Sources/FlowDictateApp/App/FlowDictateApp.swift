import AppKit
import SwiftUI

@main
struct FlowDictateApp: App {
    @StateObject private var appState = AppState()

    init() {
        // Menu-bar-only UX keeps focus on dictation in other apps.
        NSApplication.shared.setActivationPolicy(.accessory)
    }

    var body: some Scene {
        MenuBarExtra("Flow Dictate", systemImage: appState.runtimeStatus.symbolName) {
            menuContent
        }
        .menuBarExtraStyle(.window)
    }

    @ViewBuilder
    private var menuContent: some View {
        Text("Status: \(appState.runtimeStatus.menuLabel)")
            .font(.headline)

        Divider()

        Button(appState.workerRunning ? "Stop Worker" : "Start Worker") {
            if appState.workerRunning {
                appState.stopWorker()
            } else {
                appState.startWorker()
            }
        }

        Toggle(
            "Show HUD",
            isOn: Binding(
                get: { appState.showHUD },
                set: { appState.setShowHUD($0) }
            )
        )

        Toggle(
            "Launch at Login",
            isOn: Binding(
                get: { appState.launchAtLoginEnabled },
                set: { appState.setLaunchAtLogin($0) }
            )
        )

        Button("Open Settings") {
            appState.openSettingsWindow()
        }

        Button(appState.showOnboarding ? "Open Setup (Required)" : "Open Setup") {
            appState.openSetupWindow()
        }

        Button("Open Permissions Help") {
            appState.openPermissionsGuide()
        }

        Button("Open Logs") {
            appState.openLogsFolder()
        }

        if let launchError = appState.launchAtLoginManager.lastErrorMessage {
            Text("Launch-at-login error: \(launchError)")
                .font(.caption2)
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
        if let blockedMessage = appState.workerStartBlockedMessage {
            Text("Startup: \(blockedMessage)")
                .font(.caption2)
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }
        if let workerError = appState.workerManager.lastErrorMessage {
            Text("Worker: \(workerError)")
                .font(.caption2)
                .foregroundStyle(.orange)
                .fixedSize(horizontal: false, vertical: true)
        }

        Divider()

        Button("Quit") {
            appState.stopWorker()
            NSApplication.shared.terminate(nil)
        }
    }
}
