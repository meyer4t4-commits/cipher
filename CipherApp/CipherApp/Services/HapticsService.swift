import Foundation
import UIKit

final class HapticsService {
    static let shared = HapticsService()

    private let impactLight = UIImpactFeedbackGenerator(style: .light)
    private let impactMedium = UIImpactFeedbackGenerator(style: .medium)
    private let impactHeavy = UIImpactFeedbackGenerator(style: .heavy)
    private let notificationFeedback = UINotificationFeedbackGenerator()
    private let selectionFeedback = UISelectionFeedbackGenerator()

    private init() {
        impactLight.prepare()
        impactMedium.prepare()
        impactHeavy.prepare()
        notificationFeedback.prepare()
        selectionFeedback.prepare()
    }

    func lightTap() {
        impactLight.impactOccurred()
    }

    func mediumTap() {
        impactMedium.impactOccurred()
    }

    func heavyTap() {
        impactHeavy.impactOccurred()
    }

    func success() {
        notificationFeedback.notificationOccurred(.success)
    }

    func warning() {
        notificationFeedback.notificationOccurred(.warning)
    }

    func error() {
        notificationFeedback.notificationOccurred(.error)
    }

    func selection() {
        selectionFeedback.selectionChanged()
    }

    func prepare() {
        impactLight.prepare()
        impactMedium.prepare()
        notificationFeedback.prepare()
    }
}
