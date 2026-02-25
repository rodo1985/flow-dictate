import AppKit
import AVFoundation
import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var runtimeStatus: RuntimeStatus = .idle
    @Published var showHUD: Bool
    @Published var showOnboarding: Bool
    @Published var doctorReport: DoctorReport?
    @Published var onboardingErrorMessage: String?
    @Published var isDoctorReportLoading: Bool = false
    @Published var workerStartBlockedMessage: String?
    @Published private(set) var appSettings: AppSettings

    let workerManager: WorkerManager
    let launchAtLoginManager: LaunchAtLoginManager

    private let hudController = HUDWindowController()
    private let onboardingWindowController = OnboardingWindowController()
    private let settingsWindowController = SettingsWindowController()
    private let settingsStore: SettingsStore
    private let defaults: UserDefaults
    private let logStore: AppLogStore
    private let showHUDDefaultsKey = "FlowDictate.ShowHUD"
    private let onboardingDefaultsKey = "FlowDictate.OnboardingComplete"
    private var idleResetTask: Task<Void, Never>?

    init(
        workerManager: WorkerManager = WorkerManager(),
        launchAtLoginManager: LaunchAtLoginManager = LaunchAtLoginManager(),
        settingsStore: SettingsStore = SettingsStore(),
        defaults: UserDefaults = .standard,
        logStore: AppLogStore = .shared
    ) {
        self.workerManager = workerManager
        self.launchAtLoginManager = launchAtLoginManager
        self.settingsStore = settingsStore
        self.defaults = defaults
        self.logStore = logStore
        self.showHUD = defaults.object(forKey: showHUDDefaultsKey) as? Bool ?? true
        self.showOnboarding = !defaults.bool(forKey: onboardingDefaultsKey)
        self.appSettings = AppSettings(
            hotkeyExpression: AppSettingsDefaults.defaultHotkeyExpression,
            hasAPIKey: false
        )

        workerManager.onEvent = { [weak self] event in
            self?.handleWorkerEvent(event)
        }

        log("AppState initialized. show_onboarding=\(showOnboarding) show_hud=\(showHUD)")

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

    var settingsHotkeyExpression: String {
        appSettings.hotkeyExpression
    }

    var settingsHasAPIKey: Bool {
        appSettings.hasAPIKey
    }

    func setShowHUD(_ enabled: Bool) {
        showHUD = enabled
        defaults.set(enabled, forKey: showHUDDefaultsKey)
        log("HUD preference updated: \(enabled)")
        if !enabled {
            hudController.hide()
        }
    }

    func setLaunchAtLogin(_ enabled: Bool) {
        log("Launch-at-login preference update requested: \(enabled)")
        launchAtLoginManager.setEnabled(enabled)
    }

    func openSettingsWindow() {
        log("Opening settings window.")
        settingsWindowController.show(appState: self)
    }

    func saveSettings(
        apiKeyInput: String,
        hotkeyExpression: String
    ) -> Result<String, AppSettingsError> {
        do {
            let canonicalHotkey = try settingsStore.saveHotkeyExpression(hotkeyExpression)
            if !apiKeyInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                try settingsStore.saveAPIKey(apiKeyInput)
            }
            try refreshSettingsFromStore()
            guard appSettings.hasAPIKey else {
                workerStartBlockedMessage = AppSettingsError.missingAPIKey.localizedDescription
                runtimeStatus = .error(AppSettingsError.missingAPIKey.localizedDescription)
                log("Settings saved without API key. Worker remains blocked until key is added.")
                return .failure(.missingAPIKey)
            }
            restartWorkerAfterSettingsChange()
            logEffectiveRuntimeSummary()
            return .success(canonicalHotkey)
        } catch let appSettingsError as AppSettingsError {
            log("Saving settings failed: \(appSettingsError.localizedDescription)")
            return .failure(appSettingsError)
        } catch {
            log("Saving settings failed: \(error.localizedDescription)")
            return .failure(.keychainFailure(error.localizedDescription))
        }
    }

    func clearStoredAPIKey() -> Result<Void, AppSettingsError> {
        do {
            try settingsStore.clearAPIKey()
            try refreshSettingsFromStore()
            stopWorker()
            workerStartBlockedMessage = AppSettingsError.missingAPIKey.localizedDescription
            runtimeStatus = .error(AppSettingsError.missingAPIKey.localizedDescription)
            log("API key cleared. Worker start will be blocked until a new key is saved.")
            return .success(())
        } catch let appSettingsError as AppSettingsError {
            log("Clearing API key failed: \(appSettingsError.localizedDescription)")
            return .failure(appSettingsError)
        } catch {
            log("Clearing API key failed: \(error.localizedDescription)")
            return .failure(.keychainFailure(error.localizedDescription))
        }
    }

    func startWorker() {
        log("Starting worker from app state.")
        do {
            let launchConfiguration = try resolveWorkerLaunchConfiguration()
            log(
                "Effective runtime config: backend=\(AppSettingsDefaults.forcedBackend) "
                    + "output_mode=\(AppSettingsDefaults.forcedOutputMode) "
                    + "insertion_strategy=\(AppSettingsDefaults.forcedInsertionStrategy) "
                    + "hotkey=\(launchConfiguration.hotkeyExpression) "
                    + "key_present=\(launchConfiguration.hasAPIKey)"
            )
            workerManager.start(
                workingDirectory: repositoryRootURL(),
                environment: launchConfiguration.environment
            )
            workerStartBlockedMessage = nil
            runtimeStatus = .idle
        } catch let appSettingsError as AppSettingsError {
            handleWorkerStartBlocked(error: appSettingsError)
        } catch {
            handleWorkerStartBlocked(error: .keychainFailure(error.localizedDescription))
        }
    }

    func stopWorker() {
        log("Stopping worker from app state.")
        workerManager.stop()
        runtimeStatus = .idle
        hudController.hide()
    }

    func loadDoctorReport(promptPermissions: Bool = false) {
        guard !isDoctorReportLoading else {
            log("Skipping doctor report request because one is already running.")
            return
        }
        log("Loading doctor report (prompt_permissions=\(promptPermissions)).")
        onboardingErrorMessage = nil
        isDoctorReportLoading = true
        Task {
            do {
                let report = try await workerManager.runDoctorReport(
                    workingDirectory: repositoryRootURL(),
                    environment: doctorEnvironment(),
                    promptPermissions: promptPermissions
                )
                await MainActor.run {
                    self.doctorReport = report
                    if !report.allRequiredGranted {
                        // Keep setup mode active while required permissions are missing
                        // so the menu label and setup affordance remain obvious.
                        self.showOnboarding = true
                    }
                    self.isDoctorReportLoading = false
                    self.log("Doctor report loaded. all_required_granted=\(report.allRequiredGranted)")
                }
            } catch {
                await MainActor.run {
                    self.onboardingErrorMessage = error.localizedDescription
                    self.isDoctorReportLoading = false
                    self.log("Doctor report failed: \(error.localizedDescription)")
                }
            }
        }
    }

    func completeOnboarding() {
        log("Onboarding completed by user.")
        defaults.set(true, forKey: onboardingDefaultsKey)
        showOnboarding = false
        onboardingWindowController.close()
    }

    func openSetupWindow() {
        log("Opening setup window.")
        showOnboarding = true
        onboardingWindowController.show(appState: self)
    }

    func openPermissionsGuide() {
        log("Opening macOS Privacy settings deep link.")
        openPrivacySettingsPane(anchor: "Privacy")
    }

    func requestPermissionsFromSystem() {
        log("Permission assistance request triggered from onboarding UI.")
        NSApp.activate(ignoringOtherApps: true)

        guard let report = doctorReport else {
            // If we do not have a report snapshot yet, open the generic privacy page
            // so users still get a concrete next step.
            openPermissionsGuide()
            return
        }

        if !report.microphone.granted {
            assistMicrophonePermissionFlow()
        } else if !report.accessibility.granted {
            openAccessibilityPermissions()
            scheduleDoctorRefresh()
        } else if !report.inputMonitoring.granted {
            openInputMonitoringPermissions()
            scheduleDoctorRefresh()
        } else {
            openPermissionsGuide()
            scheduleDoctorRefresh()
        }
    }

    func openMicrophonePermissions() {
        log("Opening Microphone privacy pane.")
        openPrivacySettingsPane(anchor: "Privacy_Microphone")
    }

    func openAccessibilityPermissions() {
        log("Opening Accessibility privacy pane.")
        openPrivacySettingsPane(anchor: "Privacy_Accessibility")
    }

    func openInputMonitoringPermissions() {
        log("Opening Input Monitoring privacy pane.")
        openPrivacySettingsPane(anchor: "Privacy_ListenEvent")
    }

    func openLogsFolder() {
        log("Opening log file in Finder.")
        NSWorkspace.shared.activateFileViewerSelecting([logStore.logFileURL])
    }

    private func handleWorkerEvent(_ event: WorkerRuntimeEvent) {
        log("Received worker event in app state: \(event.event)")
        idleResetTask?.cancel()
        switch event.event {
        case "service_ready":
            runtimeStatus = .idle
            log(
                "Worker service_ready payload: backend=\(event.backend ?? "unknown") "
                    + "output_mode=\(event.outputMode ?? "unknown") "
                    + "insertion_strategy=\(event.insertionStrategy ?? "unknown") "
                    + "hotkey=\(event.hotkey ?? "unknown") "
                    + "config_source=\(event.configSource ?? "unknown")"
            )
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
        log("App finished launching.")
        do {
            try refreshSettingsFromStore()
        } catch {
            onboardingErrorMessage = error.localizedDescription
            log("Failed to load app settings at launch: \(error.localizedDescription)")
        }
        startWorker()
        Task {
            await verifySetupVisibilityForLaunch()
        }
    }

    private func verifySetupVisibilityForLaunch() async {
        guard !isDoctorReportLoading else {
            log("Launch-time doctor check skipped because another check is in progress.")
            return
        }

        if showOnboarding {
            log("Showing onboarding at launch because onboarding is not complete.")
            openSetupWindow()
            return
        }

        isDoctorReportLoading = true
        do {
            let report = try await workerManager.runDoctorReport(
                workingDirectory: repositoryRootURL(),
                environment: doctorEnvironment()
            )
            doctorReport = report
            isDoctorReportLoading = false
            if !report.allRequiredGranted {
                showOnboarding = true
                log("Showing onboarding at launch because required permissions are missing.")
                openSetupWindow()
            }
        } catch {
            // If preflight cannot run, we still force setup visibility so users have
            // a deterministic recovery path without hunting for menu bar controls.
            onboardingErrorMessage = "Unable to run permission checks: \(error.localizedDescription)"
            isDoctorReportLoading = false
            showOnboarding = true
            log("Showing onboarding at launch because doctor check failed: \(error.localizedDescription)")
            openSetupWindow()
        }
    }

    private func repositoryRootURL() -> URL {
        if let configuredPath = ProcessInfo.processInfo.environment["FLOW_DICTATE_REPO_ROOT"],
           !configuredPath.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return URL(fileURLWithPath: configuredPath)
        }

        return URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    }

    private func doctorEnvironment() -> [String: String] {
        ProcessInfo.processInfo.environment
    }

    private func resolveWorkerLaunchConfiguration() throws -> WorkerLaunchConfiguration {
        let settingsSnapshot = try settingsStore.loadSettings(repositoryRootURL: repositoryRootURL())
        appSettings = settingsSnapshot.appSettings
        if let migrationWarning = settingsSnapshot.migrationWarning {
            log("Settings migration warning: \(migrationWarning)")
        }

        return try AppRuntimeEnvironmentBuilder.build(
            baseEnvironment: ProcessInfo.processInfo.environment,
            runtimeSettings: settingsSnapshot.runtimeSettings
        )
    }

    private func refreshSettingsFromStore() throws {
        let settingsSnapshot = try settingsStore.loadSettings(repositoryRootURL: repositoryRootURL())
        appSettings = settingsSnapshot.appSettings
        if let migrationWarning = settingsSnapshot.migrationWarning {
            log("Settings migration warning: \(migrationWarning)")
        }
    }

    private func restartWorkerAfterSettingsChange() {
        if workerRunning {
            stopWorker()
        }
        startWorker()
    }

    private func logEffectiveRuntimeSummary() {
        log(
            "Effective runtime config: backend=\(AppSettingsDefaults.forcedBackend) "
                + "output_mode=\(AppSettingsDefaults.forcedOutputMode) "
                + "insertion_strategy=\(AppSettingsDefaults.forcedInsertionStrategy) "
                + "hotkey=\(appSettings.hotkeyExpression) "
                + "key_present=\(appSettings.hasAPIKey)"
        )
    }

    private func handleWorkerStartBlocked(error: AppSettingsError) {
        let message = error.localizedDescription
        workerStartBlockedMessage = message
        runtimeStatus = .error(message)
        showOnboarding = true
        log("Skipping worker start because required settings are missing/invalid: \(message)")
        openSettingsWindow()
    }

    private func log(_ message: String) {
        logStore.append(category: "app", message: message)
    }

    private func assistMicrophonePermissionFlow() {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        log(
            "Assisting microphone permission. app_status="
                + "\(microphoneAuthorizationStatusLabel(status))."
        )

        if status == .notDetermined {
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                Task { @MainActor in
                    self.log("App microphone prompt completed. granted=\(granted)")
                    self.scheduleDoctorRefresh(after: 0.6)
                }
            }
        }

        openMicrophonePermissions()
        scheduleDoctorRefresh()
    }

    private func microphoneAuthorizationStatusLabel(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .notDetermined:
            return "not_determined"
        case .restricted:
            return "restricted"
        case .denied:
            return "denied"
        case .authorized:
            return "authorized"
        @unknown default:
            return "unknown"
        }
    }

    private func scheduleDoctorRefresh(after seconds: Double = 0.4) {
        // macOS privacy changes can take a short moment to propagate to checks.
        Task {
            try? await Task.sleep(for: .seconds(seconds))
            await MainActor.run {
                self.loadDoctorReport()
            }
        }
    }

    private func openPrivacySettingsPane(anchor: String) {
        guard let paneURL = URL(
            string: "x-apple.systempreferences:com.apple.preference.security?\(anchor)"
        ) else {
            return
        }

        let opened = NSWorkspace.shared.open(paneURL)
        if !opened, anchor != "Privacy" {
            // Fall back to the generic Privacy page if a specific anchor is not
            // supported on this macOS build.
            openPrivacySettingsPane(anchor: "Privacy")
        }
    }
}
