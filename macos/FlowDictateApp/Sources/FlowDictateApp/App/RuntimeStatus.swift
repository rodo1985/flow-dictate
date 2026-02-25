import Foundation

enum RuntimeStatus: Equatable {
    case idle
    case recording
    case transcribing
    case success
    case error(String)

    var menuLabel: String {
        switch self {
        case .idle:
            return "Idle"
        case .recording:
            return "Recording"
        case .transcribing:
            return "Transcribing"
        case .success:
            return "Ready"
        case let .error(message):
            return "Error: \(message)"
        }
    }

    var symbolName: String {
        switch self {
        case .idle:
            return "mic"
        case .recording:
            return "mic.fill"
        case .transcribing:
            return "arrow.triangle.2.circlepath.circle.fill"
        case .success:
            return "checkmark.circle.fill"
        case .error:
            return "exclamationmark.triangle.fill"
        }
    }
}
