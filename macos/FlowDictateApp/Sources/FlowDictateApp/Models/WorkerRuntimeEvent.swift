import Foundation

enum JSONValue: Decodable, Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
            return
        }
        if let value = try? container.decode(Bool.self) {
            self = .bool(value)
            return
        }
        if let value = try? container.decode(Int.self) {
            self = .int(value)
            return
        }
        if let value = try? container.decode(Double.self) {
            self = .double(value)
            return
        }
        if let value = try? container.decode(String.self) {
            self = .string(value)
            return
        }
        if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
            return
        }
        if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
            return
        }
        throw DecodingError.typeMismatch(
            JSONValue.self,
            DecodingError.Context(
                codingPath: decoder.codingPath,
                debugDescription: "Unsupported JSON value in daemon event payload."
            )
        )
    }

    var stringValue: String? {
        if case let .string(value) = self {
            return value
        }
        return nil
    }
}

struct WorkerRuntimeEvent: Decodable, Equatable {
    let event: String
    let occurredAtUTC: String
    let payload: [String: JSONValue]

    enum CodingKeys: String, CodingKey {
        case event
        case occurredAtUTC = "occurred_at_utc"
        case payload
    }

    var fallbackReason: String? {
        payload["reason"]?.stringValue
    }

    var errorCode: String? {
        payload["code"]?.stringValue
    }

    var errorMessage: String? {
        payload["message"]?.stringValue
    }
}
