import Foundation

@MainActor
final class AppLogStore {
    static let shared = AppLogStore()

    let logDirectoryURL: URL
    let logFileURL: URL

    private let fileManager: FileManager
    private let timestampFormatter = ISO8601DateFormatter()

    private init(fileManager: FileManager = .default) {
        self.fileManager = fileManager

        let libraryDirectory = fileManager.urls(for: .libraryDirectory, in: .userDomainMask).first
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library")

        self.logDirectoryURL = libraryDirectory
            .appendingPathComponent("Logs", isDirectory: true)
            .appendingPathComponent("FlowDictate", isDirectory: true)
        self.logFileURL = logDirectoryURL.appendingPathComponent("flow-dictate-app.log")
        self.timestampFormatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]

        prepareLogStorage()
    }

    func append(category: String, message: String) {
        let normalizedMessage = message
            .replacingOccurrences(of: "\n", with: "\\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalizedMessage.isEmpty else {
            return
        }

        prepareLogStorage()

        let timestamp = timestampFormatter.string(from: Date())
        let line = "[\(timestamp)] [\(category)] \(normalizedMessage)\n"
        guard let data = line.data(using: .utf8) else {
            return
        }

        do {
            let handle = try FileHandle(forWritingTo: logFileURL)
            defer {
                try? handle.close()
            }
            try handle.seekToEnd()
            try handle.write(contentsOf: data)
        } catch {
            // Logging should never interrupt app runtime; write failures are ignored.
        }
    }

    private func prepareLogStorage() {
        if !fileManager.fileExists(atPath: logDirectoryURL.path) {
            try? fileManager.createDirectory(
                at: logDirectoryURL,
                withIntermediateDirectories: true
            )
        }

        if !fileManager.fileExists(atPath: logFileURL.path) {
            fileManager.createFile(atPath: logFileURL.path, contents: nil)
        }
    }
}
