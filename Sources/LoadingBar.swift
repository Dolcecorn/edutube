import UIKit

/// Barra delgada abajo de la pantalla que avisa que algo está cargando, sin tapar el contenido.
final class LoadingBar: UIView {
    private let segment = CAGradientLayer()
    private var visible = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        isUserInteractionEnabled = false
        backgroundColor = UIColor(white: 1, alpha: 0.08)
        clipsToBounds = true
        alpha = 0
        let red = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 1)
        segment.colors = [red.withAlphaComponent(0).cgColor, red.cgColor, UIColor(red: 1, green: 0.69, blue: 0.6, alpha: 1).cgColor]
        segment.locations = [0, 0.7, 1]
        segment.startPoint = CGPoint(x: 0, y: 0.5)
        segment.endPoint = CGPoint(x: 1, y: 0.5)
        layer.addSublayer(segment)
    }

    required init?(coder: NSCoder) { fatalError() }

    override func layoutSubviews() {
        super.layoutSubviews()
        segment.frame = CGRect(x: 0, y: 0, width: bounds.width * 0.4, height: bounds.height)
        if visible { animate() }
    }

    func show() {
        guard !visible else { return }
        visible = true
        animate()
        UIView.animate(withDuration: 0.2) { self.alpha = 1 }
    }

    func hide() {
        guard visible else { return }
        visible = false
        UIView.animate(withDuration: 0.3, animations: { self.alpha = 0 }) { _ in
            if !self.visible { self.segment.removeAllAnimations() }
        }
    }

    /// El tramo rojo cruza la barra de izquierda a derecha una y otra vez.
    private func animate() {
        segment.removeAllAnimations()
        let w = bounds.width
        let move = CABasicAnimation(keyPath: "position.x")
        move.fromValue = -w * 0.2
        move.toValue = w * 1.2
        move.duration = 1.1
        move.repeatCount = .infinity
        move.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
        segment.add(move, forKey: "move")
    }
}
