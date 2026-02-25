import Foundation

struct DoctorPermissionCheck: Decodable, Equatable {
    let name: String
    let granted: Bool
    let state: String
    let details: String
    let remediation: String?
}

struct DoctorReport: Decodable, Equatable {
    let allRequiredGranted: Bool
    let microphone: DoctorPermissionCheck
    let accessibility: DoctorPermissionCheck
    let inputMonitoring: DoctorPermissionCheck

    enum CodingKeys: String, CodingKey {
        case allRequiredGranted = "all_required_granted"
        case microphone
        case accessibility
        case inputMonitoring = "input_monitoring"
    }
}
