import Foundation

enum HotkeyValidationError: LocalizedError, Equatable {
    case emptyExpression
    case invalidToken(String)
    case modifierOnly

    var errorDescription: String? {
        switch self {
        case .emptyExpression:
            return "Hotkey cannot be empty."
        case let .invalidToken(token):
            return "Unsupported key token '\(token)'."
        case .modifierOnly:
            return "Hotkey must include a non-modifier key."
        }
    }
}

enum HotkeyValidator {
    private static let modifierTokens: Set<String> = ["cmd", "ctrl", "shift", "alt"]
    private static let specialKeyOrder: [String: Int] = [
        "space": 10,
        "enter": 11,
        "tab": 12,
        "esc": 13,
    ]
    private static let modifierOrder: [String: Int] = [
        "ctrl": 0,
        "cmd": 1,
        "shift": 2,
        "alt": 3,
    ]
    private static let aliasMap: [String: String] = [
        "cmd": "cmd",
        "command": "cmd",
        "meta": "cmd",
        "ctrl": "ctrl",
        "control": "ctrl",
        "shift": "shift",
        "alt": "alt",
        "option": "alt",
        "space": "space",
        "enter": "enter",
        "return": "enter",
        "tab": "tab",
        "esc": "esc",
        "escape": "esc",
    ]

    static func validate(expression: String) throws -> String {
        let rawTokens = expression
            .split(separator: "+", omittingEmptySubsequences: false)
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() }
            .filter { !$0.isEmpty }

        guard !rawTokens.isEmpty else {
            throw HotkeyValidationError.emptyExpression
        }

        var normalizedTokens = Set<String>()
        for rawToken in rawTokens {
            guard let normalized = normalize(token: rawToken) else {
                throw HotkeyValidationError.invalidToken(rawToken)
            }
            normalizedTokens.insert(normalized)
        }

        if normalizedTokens.isSubset(of: modifierTokens) {
            throw HotkeyValidationError.modifierOnly
        }

        return canonicalExpression(from: normalizedTokens)
    }

    private static func normalize(token: String) -> String? {
        if let aliasValue = aliasMap[token] {
            return aliasValue
        }

        guard token.count == 1 else {
            return nil
        }

        if token.rangeOfCharacter(from: .controlCharacters) != nil {
            return nil
        }

        return token
    }

    private static func canonicalExpression(from tokens: Set<String>) -> String {
        tokens
            .sorted(by: tokenSortComparator(_:_:))
            .joined(separator: "+")
    }

    private static func tokenSortComparator(_ lhs: String, _ rhs: String) -> Bool {
        sortPriority(for: lhs) < sortPriority(for: rhs)
    }

    private static func sortPriority(for token: String) -> (Int, Int, String) {
        if let order = modifierOrder[token] {
            return (0, order, token)
        }
        if let order = specialKeyOrder[token] {
            return (1, order, token)
        }
        return (2, 0, token)
    }
}
