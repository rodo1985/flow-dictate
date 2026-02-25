import Foundation
import ServiceManagement

@MainActor
final class LaunchAtLoginManager: ObservableObject {
    @Published private(set) var isEnabled: Bool = false
    @Published private(set) var lastErrorMessage: String?

    init() {
        refresh()
    }

    func refresh() {
        if #available(macOS 13.0, *) {
            isEnabled = SMAppService.mainApp.status == .enabled
        } else {
            isEnabled = false
        }
    }

    func setEnabled(_ enabled: Bool) {
        if #available(macOS 13.0, *) {
            do {
                if enabled {
                    try SMAppService.mainApp.register()
                } else {
                    try SMAppService.mainApp.unregister()
                }
                lastErrorMessage = nil
            } catch {
                lastErrorMessage = error.localizedDescription
            }
            refresh()
            return
        }

        lastErrorMessage = "Launch at login requires macOS 13 or newer."
        isEnabled = false
    }
}
