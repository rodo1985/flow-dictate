import Foundation

@MainActor
final class WorkerManager: ObservableObject {
    @Published private(set) var isRunning: Bool = false
    @Published private(set) var lastErrorMessage: String?

    var onEvent: ((WorkerRuntimeEvent) -> Void)?

    private let restartBackoffSeconds: [Double] = [1, 2, 4, 8, 10]
    private var restartAttempt: Int = 0
    private var shouldRestartAfterTermination: Bool = false

    private var process: Process?
    private var stdoutPipe: Pipe?
    private var stderrPipe: Pipe?

    private var stdoutBuffer = Data()
    private var lastWorkingDirectory: URL?
    private var lastEnvironment: [String: String]?
    private let logStore: AppLogStore

    init(logStore: AppLogStore = .shared) {
        self.logStore = logStore
        log("Worker manager initialized.")
    }

    func start(workingDirectory: URL, environment: [String: String]) {
        guard process == nil else {
            log("Start requested while worker is already running. Ignoring duplicate request.")
            return
        }

        lastErrorMessage = nil
        shouldRestartAfterTermination = true
        lastWorkingDirectory = workingDirectory
        lastEnvironment = environment
        log(
            "Starting worker with cwd=\(workingDirectory.path) "
                + "backend=\(environment["FLOW_DICTATE_BACKEND"] ?? "unknown") "
                + "output_mode=\(environment["FLOW_DICTATE_OUTPUT_MODE"] ?? "unknown") "
                + "insertion_strategy=\(environment["FLOW_DICTATE_ACTIVE_APP_INSERTION_STRATEGY"] ?? "unknown") "
                + "hotkey=\(environment["FLOW_DICTATE_HOTKEY"] ?? "unknown") "
                + "key_present=\(((environment["OPENAI_API_KEY"] ?? "").isEmpty == false))"
        )
        launchWorker(workingDirectory: workingDirectory, environment: environment)
    }

    func stop() {
        log("Stop requested for worker process.")
        shouldRestartAfterTermination = false
        restartAttempt = 0
        process?.terminate()
        cleanupAfterTermination()
    }

    func runDoctorReport(
        workingDirectory: URL,
        environment: [String: String],
        promptPermissions: Bool = false
    ) async throws -> DoctorReport {
        guard let uvExecutableURL = resolveUVExecutableURL() else {
            let message = (
                "Unable to locate uv executable. Reinstall Flow Dictate "
                    + "or set FLOW_DICTATE_UV_BIN."
            )
            log(message)
            throw NSError(
                domain: "FlowDictateWorker",
                code: 127,
                userInfo: [NSLocalizedDescriptionKey: message]
            )
        }
        log(
            "Running doctor preflight from app shell "
                + "(prompt_permissions=\(promptPermissions), uv_path=\(uvExecutableURL.path))."
        )
        let command = Process()
        command.executableURL = uvExecutableURL
        var commandArguments = [
            "run",
            "flow-dictate",
            "doctor",
            "--json",
        ]
        if promptPermissions {
            commandArguments.append("--prompt-permissions")
        }
        command.arguments = commandArguments
        command.currentDirectoryURL = workingDirectory
        command.environment = environment
        let outputPipe = Pipe()
        let errorPipe = Pipe()
        command.standardOutput = outputPipe
        command.standardError = errorPipe

        try command.run()
        command.waitUntilExit()

        let outputData = outputPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = errorPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrText = String(decoding: stderrData, as: UTF8.self)
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if !stderrText.isEmpty {
            log("doctor stderr: \(stderrText)")
        }
        log("doctor exited with status \(command.terminationStatus).")
        guard command.terminationStatus == 0 || command.terminationStatus == 1 else {
            throw NSError(
                domain: "FlowDictateWorker",
                code: Int(command.terminationStatus),
                userInfo: [NSLocalizedDescriptionKey: "doctor command failed: \(stderrText)"]
            )
        }

        let decoder = JSONDecoder()
        let report = try decoder.decode(DoctorReport.self, from: outputData)
        log(
            "doctor result: all_required_granted=\(report.allRequiredGranted) "
                + "microphone=\(report.microphone.state) "
                + "accessibility=\(report.accessibility.state) "
                + "input_monitoring=\(report.inputMonitoring.state)"
        )
        return report
    }

    private func launchWorker(workingDirectory: URL, environment: [String: String]) {
        guard let uvExecutableURL = resolveUVExecutableURL() else {
            let message = (
                "Unable to locate uv executable. Reinstall Flow Dictate "
                    + "or set FLOW_DICTATE_UV_BIN."
            )
            lastErrorMessage = message
            // Missing uv will not self-heal with restart backoff, so we disable
            // restart and surface a stable actionable message in menu + logs.
            shouldRestartAfterTermination = false
            log(message)
            return
        }

        let worker = Process()
        worker.executableURL = uvExecutableURL
        worker.arguments = [
            "run",
            "flow-dictate",
            "daemon",
            "--output",
            "active-app",
        ]
        worker.currentDirectoryURL = workingDirectory
        worker.environment = environment

        let nextStdoutPipe = Pipe()
        let nextStderrPipe = Pipe()
        worker.standardOutput = nextStdoutPipe
        worker.standardError = nextStderrPipe

        worker.terminationHandler = { [weak self] terminatedProcess in
            Task { @MainActor in
                self?.handleTermination(status: terminatedProcess.terminationStatus)
            }
        }

        configureOutputHandlers(stdout: nextStdoutPipe, stderr: nextStderrPipe)

        do {
            try worker.run()
            process = worker
            stdoutPipe = nextStdoutPipe
            stderrPipe = nextStderrPipe
            isRunning = true
            log(
                "Worker started successfully (pid=\(worker.processIdentifier), "
                    + "uv_path=\(uvExecutableURL.path))."
            )
        } catch {
            lastErrorMessage = "Unable to start daemon worker: \(error.localizedDescription)"
            log("Worker failed to start: \(error.localizedDescription)")
            scheduleRestartIfNeeded()
        }
    }

    private func configureOutputHandlers(stdout: Pipe, stderr: Pipe) {
        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                return
            }

            Task { @MainActor in
                self?.consumeStdoutChunk(data)
            }
        }

        stderr.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else {
                return
            }

            let stderrLine = String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            guard !stderrLine.isEmpty else {
                return
            }

            Task { @MainActor in
                self?.log("worker stderr: \(stderrLine)")
                self?.lastErrorMessage = stderrLine
            }
        }
    }

    private func consumeStdoutChunk(_ chunk: Data) {
        stdoutBuffer.append(chunk)

        while true {
            guard let newlineIndex = stdoutBuffer.firstIndex(of: 0x0A) else {
                break
            }

            let lineData = stdoutBuffer[..<newlineIndex]
            stdoutBuffer = Data(stdoutBuffer[(newlineIndex + 1)...])

            guard !lineData.isEmpty else {
                continue
            }

            do {
                let event = try JSONDecoder().decode(WorkerRuntimeEvent.self, from: Data(lineData))
                log("worker event: \(event.event)")
                onEvent?(event)
            } catch {
                // Invalid JSON from stdout should be visible to operators because this
                // stream is expected to contain only daemon runtime events.
                lastErrorMessage = "Invalid daemon event: \(error.localizedDescription)"
                let rawLine = String(decoding: lineData, as: UTF8.self)
                log("Invalid daemon event JSON: \(rawLine)")
            }
        }
    }

    private func handleTermination(status: Int32) {
        cleanupAfterTermination()
        log("Worker terminated with status \(status). restart_enabled=\(shouldRestartAfterTermination)")
        if shouldRestartAfterTermination {
            lastErrorMessage = "Daemon worker exited with status \(status). Restarting."
            scheduleRestartIfNeeded()
        }
    }

    private func scheduleRestartIfNeeded() {
        guard shouldRestartAfterTermination else {
            return
        }
        guard let workingDirectory = lastWorkingDirectory, let environment = lastEnvironment else {
            return
        }

        let index = min(restartAttempt, restartBackoffSeconds.count - 1)
        let delaySeconds = restartBackoffSeconds[index]
        restartAttempt += 1
        log("Scheduling worker restart attempt \(restartAttempt) after \(delaySeconds)s.")

        Task {
            try? await Task.sleep(for: .seconds(delaySeconds))
            await MainActor.run {
                guard self.process == nil, self.shouldRestartAfterTermination else {
                    return
                }
                self.launchWorker(workingDirectory: workingDirectory, environment: environment)
            }
        }
    }

    private func cleanupAfterTermination() {
        stdoutPipe?.fileHandleForReading.readabilityHandler = nil
        stderrPipe?.fileHandleForReading.readabilityHandler = nil
        stdoutPipe = nil
        stderrPipe = nil
        process = nil
        stdoutBuffer = Data()
        isRunning = false
        log("Worker cleanup completed.")
    }

    private func log(_ message: String) {
        logStore.append(category: "worker", message: message)
    }

    private func resolveUVExecutableURL() -> URL? {
        let fileManager = FileManager.default

        if let configuredPath = ProcessInfo.processInfo.environment["FLOW_DICTATE_UV_BIN"]?
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !configuredPath.isEmpty {
            if fileManager.isExecutableFile(atPath: configuredPath) {
                return URL(fileURLWithPath: configuredPath)
            }
            log("Configured FLOW_DICTATE_UV_BIN is not executable: \(configuredPath)")
        }

        if let pathEntries = ProcessInfo.processInfo.environment["PATH"]?
            .split(separator: ":")
            .map(String.init) {
            for entry in pathEntries {
                let candidatePath = URL(fileURLWithPath: entry)
                    .appendingPathComponent("uv")
                    .path
                if fileManager.isExecutableFile(atPath: candidatePath) {
                    return URL(fileURLWithPath: candidatePath)
                }
            }
        }

        let fallbackCandidates = [
            "/opt/homebrew/bin/uv",
            "/usr/local/bin/uv",
            "\(NSHomeDirectory())/.local/bin/uv",
            "/usr/bin/uv",
        ]
        for candidatePath in fallbackCandidates where fileManager.isExecutableFile(atPath: candidatePath) {
            return URL(fileURLWithPath: candidatePath)
        }

        return nil
    }
}
