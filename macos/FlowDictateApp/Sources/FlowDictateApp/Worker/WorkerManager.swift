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

    func start(workingDirectory: URL, environment: [String: String]) {
        guard process == nil else {
            return
        }

        lastErrorMessage = nil
        shouldRestartAfterTermination = true
        lastWorkingDirectory = workingDirectory
        lastEnvironment = environment
        launchWorker(workingDirectory: workingDirectory, environment: environment)
    }

    func stop() {
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
        let command = Process()
        command.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        var commandArguments = [
            "uv",
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
        guard command.terminationStatus == 0 || command.terminationStatus == 1 else {
            let stderrText = String(decoding: stderrData, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
            throw NSError(
                domain: "FlowDictateWorker",
                code: Int(command.terminationStatus),
                userInfo: [NSLocalizedDescriptionKey: "doctor command failed: \(stderrText)"]
            )
        }

        let decoder = JSONDecoder()
        return try decoder.decode(DoctorReport.self, from: outputData)
    }

    private func launchWorker(workingDirectory: URL, environment: [String: String]) {
        let worker = Process()
        worker.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        worker.arguments = [
            "uv",
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
        } catch {
            lastErrorMessage = "Unable to start daemon worker: \(error.localizedDescription)"
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
                onEvent?(event)
            } catch {
                // Invalid JSON from stdout should be visible to operators because this
                // stream is expected to contain only daemon runtime events.
                lastErrorMessage = "Invalid daemon event: \(error.localizedDescription)"
            }
        }
    }

    private func handleTermination(status: Int32) {
        cleanupAfterTermination()
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
    }
}
