import SwiftUI

struct SettingsView: View {
    @ObservedObject var appState: AppState
    @State private var apiKeyInput: String = ""
    @State private var hotkeyInput: String = ""
    @State private var formMessage: String?
    @State private var formError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Flow Dictate Settings")
                .font(.title2.weight(.semibold))

            Text("App mode is fixed to active-app output with API backend. Configure only key and hotkey here.")
                .foregroundStyle(.secondary)

            runtimeBadges

            VStack(alignment: .leading, spacing: 8) {
                Text("OpenAI API Key")
                    .font(.headline)
                SecureField("sk-...", text: $apiKeyInput)
                    .textFieldStyle(.roundedBorder)
                Text(appState.settingsHasAPIKey ? "Keychain: key is configured." : "Keychain: key is missing.")
                    .font(.caption)
                    .foregroundStyle(appState.settingsHasAPIKey ? .green : .orange)
            }

            VStack(alignment: .leading, spacing: 8) {
                Text("Hotkey")
                    .font(.headline)
                TextField("cmd+shift+space", text: $hotkeyInput)
                    .textFieldStyle(.roundedBorder)
                Text("Accepted tokens: cmd, ctrl, shift, alt, space, enter, tab, esc, or printable keys.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            if let formError {
                Text(formError)
                    .font(.caption)
                    .foregroundStyle(.red)
            }
            if let formMessage {
                Text(formMessage)
                    .font(.caption)
                    .foregroundStyle(.green)
            }

            Spacer()

            HStack {
                Button("Clear API Key") {
                    clearAPIKey()
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("Save") {
                    saveSettings()
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(minWidth: 520, minHeight: 360)
        .onAppear {
            hotkeyInput = appState.settingsHotkeyExpression
        }
    }

    private var runtimeBadges: some View {
        HStack(spacing: 8) {
            settingsBadge(label: "Output mode", value: AppSettingsDefaults.forcedOutputMode)
            settingsBadge(label: "Backend", value: AppSettingsDefaults.forcedBackend)
        }
    }

    private func settingsBadge(label: String, value: String) -> some View {
        HStack(spacing: 4) {
            Text("\(label):")
                .foregroundStyle(.secondary)
            Text(value)
                .fontWeight(.semibold)
        }
        .font(.caption)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color(nsColor: .controlBackgroundColor))
        .clipShape(Capsule())
    }

    private func saveSettings() {
        formMessage = nil
        formError = nil
        switch appState.saveSettings(apiKeyInput: apiKeyInput, hotkeyExpression: hotkeyInput) {
        case let .success(canonicalHotkey):
            hotkeyInput = canonicalHotkey
            apiKeyInput = ""
            formMessage = "Settings saved. Worker reloaded with hotkey \(canonicalHotkey)."
        case let .failure(error):
            formError = error.localizedDescription
        }
    }

    private func clearAPIKey() {
        formMessage = nil
        formError = nil
        switch appState.clearStoredAPIKey() {
        case .success:
            apiKeyInput = ""
            formMessage = "OpenAI API key was removed from Keychain."
        case let .failure(error):
            formError = error.localizedDescription
        }
    }
}
