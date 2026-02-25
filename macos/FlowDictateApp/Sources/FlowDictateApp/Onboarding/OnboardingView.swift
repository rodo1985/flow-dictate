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

            Toggle("Launch at login", isOn: $launchAtLoginOptIn)
                .onChange(of: launchAtLoginOptIn) { value in
                    appState.setLaunchAtLogin(value)
                }

            HStack {
                Button("Open Privacy Settings") {
                    appState.openPermissionsGuide()
                }

                Button("Request Permissions") {
                    appState.loadDoctorReport(promptPermissions: true)
                }

                Spacer()

                Button("Done") {
                    appState.completeOnboarding()
                }
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(20)
        .frame(minWidth: 520, minHeight: 340)
        .onAppear {
            launchAtLoginOptIn = appState.launchAtLoginEnabled
            // Setup should proactively request prompts when available so users can
            // complete onboarding without running CLI commands.
            appState.loadDoctorReport(promptPermissions: true)
        }
    }

    @ViewBuilder
    private func permissionList(report: DoctorReport) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            PermissionRow(check: report.microphone)
            PermissionRow(check: report.accessibility)
            PermissionRow(check: report.inputMonitoring)
        }
    }
}

private struct PermissionRow: View {
    let check: DoctorPermissionCheck

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
        }
        .padding(.vertical, 2)
    }
}
