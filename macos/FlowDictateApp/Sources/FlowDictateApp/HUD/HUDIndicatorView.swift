import SwiftUI

struct HUDIndicatorView: View {
    let state: HUDState
    @State private var pulse = false

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial.opacity(0.95))
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .stroke(borderColor, lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.18), radius: 12, x: 0, y: 4)

            content
                .padding(16)
        }
        .frame(width: 88, height: 88)
        .onAppear {
            if state == .recording {
                pulse = true
            }
        }
    }

    @ViewBuilder
    private var content: some View {
        switch state {
        case .recording:
            Circle()
                .fill(Color.red)
                .frame(width: 24, height: 24)
                .scaleEffect(pulse ? 1.15 : 0.85)
                .animation(
                    .easeInOut(duration: 0.8).repeatForever(autoreverses: true),
                    value: pulse
                )
        case .transcribing:
            ProgressView()
                .progressViewStyle(.circular)
                .tint(Color.accentColor)
                .scaleEffect(1.3)
        case .success:
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(Color.green)
        case .error:
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 34, weight: .semibold))
                .foregroundStyle(Color.orange)
        }
    }

    private var borderColor: Color {
        switch state {
        case .recording:
            return Color.red.opacity(0.45)
        case .transcribing:
            return Color.blue.opacity(0.45)
        case .success:
            return Color.green.opacity(0.45)
        case .error:
            return Color.orange.opacity(0.45)
        }
    }
}
