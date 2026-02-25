import SwiftUI

struct OnboardingView: View {
    @ObservedObject var appState: AppState
    @State private var launchAtLoginOptIn: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Flow Dictate Setup")
                .font(.title2.weight(.semibold))

            Text("Grant permissions once and choose whether Flow Dictate should launch automatically when you sign in.")
                .foregroundStyle(.secondary)

            if let report = appState.doctorReport {
                permissionList(report: report)
            } else if let errorMessage = appState.onboardingErrorMessage {
                Text("Permission check error: \(errorMessage)")
                    .foregroundStyle(.red)
            } else {
                HStack(spacing: 8) {
                    ProgressView()
                    Text("Checking permissions...")
                        .foregroundStyle(.secondary)
                }
            }

            if appState.isDoctorReportLoading {
                HStack(spacing: 8) {
                    ProgressView()
                    Text("Refreshing permission status...")
                        .foregroundStyle(.secondary)
                }
            }

            Toggle("Launch at login", isOn: $launchAtLoginOptIn)
                .onChange(of: launchAtLoginOptIn) { value in
                    appState.setLaunchAtLogin(value)
                }

            VStack(alignment: .leading, spacing: 6) {
                Text("App Settings")
                    .font(.body.weight(.medium))
                Text(
                    appState.settingsHasAPIKey
                        ? "OpenAI API key is configured in Keychain."
                        : "OpenAI API key is missing. Add it in Settings."
                )
                .font(.caption)
                .foregroundStyle(appState.settingsHasAPIKey ? .green : .orange)
                Text("Hotkey: \(appState.settingsHotkeyExpression)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let blockedMessage = appState.workerStartBlockedMessage {
                    Text("Worker blocked: \(blockedMessage)")
                        .font(.caption)
                        .foregroundStyle(.orange)
                }
            }

            HStack {
                Button("Open Privacy Settings") {
                    appState.openPermissionsGuide()
                }

                Button("Open Settings") {
                    appState.openSettingsWindow()
                }

                Button(appState.isDoctorReportLoading ? "Requesting..." : "Request Permissions") {
                    appState.requestPermissionsFromSystem()
                }
                .disabled(appState.isDoctorReportLoading)

                Spacer()

                Button("Done") {
                    appState.completeOnboarding()
                }
                .keyboardShortcut(.defaultAction)
            }

            Text(
                "Use 'Request Permissions' to jump to the next missing permission page, "
                    + "or use the direct buttons below."
            )
            .font(.caption)
            .foregroundStyle(.secondary)
        }
        .padding(20)
        .frame(minWidth: 520, minHeight: 340)
        .onAppear {
            launchAtLoginOptIn = appState.launchAtLoginEnabled
            appState.loadDoctorReport()
        }
    }

    @ViewBuilder
    private func permissionList(report: DoctorReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            PermissionRow(
                check: report.microphone,
                actionLabel: "Open Microphone",
                action: appState.openMicrophonePermissions
            )
            PermissionRow(
                check: report.accessibility,
                actionLabel: "Open Accessibility",
                action: appState.openAccessibilityPermissions
            )
            PermissionRow(
                check: report.inputMonitoring,
                actionLabel: "Open Input Monitoring",
                action: appState.openInputMonitoringPermissions
            )
        }
    }
}

private struct PermissionRow: View {
    let check: DoctorPermissionCheck
    let actionLabel: String
    let action: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: check.granted ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(check.granted ? .green : .orange)
                .font(.system(size: 16))
                .frame(width: 18, height: 18)

            VStack(alignment: .leading, spacing: 2) {
                Text(check.name)
                    .font(.body.weight(.medium))
                Text(check.details)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if let remediation = check.remediation, !remediation.isEmpty {
                    Text("Fix: \(remediation)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer(minLength: 12)
            if !check.granted {
                Button(actionLabel) {
                    action()
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .padding(.vertical, 2)
    }
}
