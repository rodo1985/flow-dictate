import AppKit
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var runtimeStatus: RuntimeStatus = .idle
    @Published var showHUD: Bool
    @Published var showOnboarding: Bool
    @Published var doctorReport: DoctorReport?
    @Published var onboardingErrorMessage: String?

    let workerManager: WorkerManager
    let launchAtLoginManager: LaunchAtLoginManager

    private let hudController = HUDWindowController()
    private let onboardingWindowController = OnboardingWindowController()
    private let defaults = UserDefaults.standard
    private let showHUDDefaultsKey = "FlowDictate.ShowHUD"
    private let onboardingDefaultsKey = "FlowDictate.OnboardingComplete"
    private var idleResetTask: Task<Void, Never>?

    init(
        workerManager: WorkerManager = WorkerManager(),
        launchAtLoginManager: LaunchAtLoginManager = LaunchAtLoginManager()
    ) {
        self.workerManager = workerManager
        self.launchAtLoginManager = launchAtLoginManager
        self.showHUD = defaults.object(forKey: showHUDDefaultsKey) as? Bool ?? true
        self.showOnboarding = !defaults.bool(forKey: onboardingDefaultsKey)

        workerManager.onEvent = { [weak self] event in
            self?.handleWorkerEvent(event)
        }

        Task { @MainActor [weak self] in
            self?.handleAppDidFinishLaunching()
        }
    }

    var workerRunning: Bool {
        workerManager.isRunning
    }

    var launchAtLoginEnabled: Bool {
        launchAtLoginManager.isEnabled
    }

    func setShowHUD(_ enabled: Bool) {
        showHUD = enabled
        defaults.set(enabled, forKey: showHUDDefaultsKey)
        if !enabled {
            hudController.hide()
        }
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        launchAtLoginManager.setEnabled(enabled)
    }

    func startWorker() {
        workerManager.start(
            workingDirectory: repositoryRootURL(),
            environment: workerEnvironment()
        )
        runtimeStatus = .idle
    }

    func stopWorker() {
        workerManager.stop()
        runtimeStatus = .idle
        hudController.hide()
    }

    func loadDoctorReport(promptPermissions: Bool = false) {
        onboardingErrorMessage = nil
        Task {
            do {
                let report = try await workerManager.runDoctorReport(
                    workingDirectory: repositoryRootURL(),
                    environment: workerEnvironment(),
                    promptPermissions: promptPermissions
                )
                await MainActor.run {
                    self.doctorReport = report
                    if !report.allRequiredGranted {
                        // Keep setup mode active while required permissions are missing
                        // so the menu label and setup affordance remain obvious.
                        self.showOnboarding = true
                    }
                }
            } catch {
                await MainActor.run {
                    self.onboardingErrorMessage = error.localizedDescription
                }
            }
        }
    }

    func completeOnboarding() {
        defaults.set(true, forKey: onboardingDefaultsKey)
        showOnboarding = false
        onboardingWindowController.close()
    }

    func openSetupWindow() {
        showOnboarding = true
        onboardingWindowController.show(appState: self)
    }

    func openPermissionsGuide() {
        guard let guideURL = URL(
            string: "x-apple.systempreferences:com.apple.preference.security?Privacy"
        ) else {
            return
        }
        NSWorkspace.shared.open(guideURL)
    }

    private func handleWorkerEvent(_ event: WorkerRuntimeEvent) {
        idleResetTask?.cancel()
        switch event.event {
        case "service_ready":
            runtimeStatus = .idle
        case "recording_started":
            runtimeStatus = .recording
            showHUDState(.recording)
        case "transcribing_started":
            runtimeStatus = .transcribing
            showHUDState(.transcribing)
        case "insertion_succeeded":
            runtimeStatus = .success
            showHUDState(.success)
            scheduleIdleReset(after: 1.3)
        case "error":
            let message = event.errorMessage ?? "Unknown daemon error"
            runtimeStatus = .error(message)
            showHUDState(.error)
            scheduleIdleReset(after: 3.1)
        default:
            break
        }
    }

    private func scheduleIdleReset(after seconds: Double) {
        idleResetTask = Task {
            try? await Task.sleep(for: .seconds(seconds))
            await MainActor.run {
                self.runtimeStatus = .idle
            }
        }
    }

    private func showHUDState(_ state: HUDState) {
        guard showHUD else {
            return
        }
        hudController.show(state: state)
    }

    private func handleAppDidFinishLaunching() {
        startWorker()
        Task {
            await verifySetupVisibilityForLaunch()
        }
    }

    private func verifySetupVisibilityForLaunch() async {
        if showOnboarding {
            openSetupWindow()
            return
        }

        do {
            let report = try await workerManager.runDoctorReport(
                workingDirectory: repositoryRootURL(),
                environment: workerEnvironment()
            )
            doctorReport = report
            if !report.allRequiredGranted {
                showOnboarding = true
                openSetupWindow()
            }
        } catch {
            // If preflight cannot run, we still force setup visibility so users have
            // a deterministic recovery path without hunting for menu bar controls.
            onboardingErrorMessage = "Unable to run permission checks: \(error.localizedDescription)"
            showOnboarding = true
            openSetupWindow()
        }
    }

    private func workerEnvironment() -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        environment["FLOW_DICTATE_OUTPUT_MODE"] = "active-app"
        environment["FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"] = "direct-type"
        return environment
    }

    private func repositoryRootURL() -> URL {
        if let configuredPath = ProcessInfo.processInfo.environment["FLOW_DICTATE_REPO_ROOT"],
           !configuredPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return URL(fileURLWithPath: configuredPath)
        }

        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }
}
