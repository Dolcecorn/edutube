import UIKit

/**
 Animación de carga: un anillo con degradado que gira alrededor de un botón de play que "respira".
 En modo pantalla de inicio cubre todo con un fondo oscuro; en modo video solo muestra el anillo.
 */
final class LoadingView: UIView {
    private static let accent = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 1)

    private var link: CADisplayLink?
    private let start = CACurrentMediaTime()
    private var splash = true
    private(set) var visible = false

    override init(frame: CGRect) {
        super.init(frame: frame)
        isOpaque = false
        backgroundColor = .clear
        isUserInteractionEnabled = false
        contentMode = .redraw
        isHidden = true
    }

    required init?(coder: NSCoder) { fatalError() }

    /// splash = true: fondo completo con título; false: solo el anillo sobre el video.
    func show(splash: Bool) {
        self.splash = splash
        isUserInteractionEnabled = splash
        if !visible {
            visible = true
            isHidden = false
            layer.removeAllAnimations()
            alpha = splash ? 1 : 0
            if !splash { UIView.animate(withDuration: 0.2) { self.alpha = 1 } }
            startLink()
        }
        setNeedsDisplay()
    }

    func hide() {
        guard visible else { return }
        visible = false
        isUserInteractionEnabled = false
        UIView.animate(withDuration: splash ? 0.45 : 0.2, animations: { self.alpha = 0 }) { _ in
            if !self.visible {
                self.isHidden = true
                self.link?.invalidate()
                self.link = nil
            }
        }
    }

    private func startLink() {
        guard link == nil else { return }
        let l = CADisplayLink(target: WeakTarget(self), selector: #selector(WeakTarget.tick))
        l.add(to: .main, forMode: .common)
        link = l
    }

    override func draw(_ rect: CGRect) {
        guard let c = UIGraphicsGetCurrentContext() else { return }
        let w = bounds.width, h = bounds.height
        let t = CGFloat(CACurrentMediaTime() - start)
        let cx = w / 2, cy = splash ? h / 2 - 20 : h / 2
        let r: CGFloat = splash ? 46 : 34
        let space = CGColorSpaceCreateDeviceRGB()

        if splash {
            let bg = [UIColor(red: 0x1C / 255, green: 0x20 / 255, blue: 0x30 / 255, alpha: 1).cgColor,
                      UIColor(red: 0x07 / 255, green: 0x08 / 255, blue: 0x0C / 255, alpha: 1).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: space, colors: bg, locations: [0, 1]) {
                c.drawRadialGradient(g, startCenter: CGPoint(x: w / 2, y: h / 2), startRadius: 0,
                                     endCenter: CGPoint(x: w / 2, y: h / 2), endRadius: max(w, h) * 0.7,
                                     options: .drawsAfterEndLocation)
            }
        }

        // Halo que late suavemente.
        let pulse = 0.5 + 0.5 * sin(t * .pi * 1.4)
        let glowR = r * (1.9 + 0.25 * pulse)
        let glow = [Self.accent.withAlphaComponent((70 + 50 * pulse) / 255).cgColor,
                    Self.accent.withAlphaComponent(0).cgColor] as CFArray
        if let g = CGGradient(colorsSpace: space, colors: glow, locations: [0, 1]) {
            c.drawRadialGradient(g, startCenter: CGPoint(x: cx, y: cy), startRadius: 0,
                                 endCenter: CGPoint(x: cx, y: cy), endRadius: glowR, options: [])
        }

        // Disco y pista del anillo.
        c.setFillColor(UIColor(red: 0x10 / 255, green: 0x12 / 255, blue: 0x18 / 255, alpha: 0.8).cgColor)
        c.fillEllipse(in: CGRect(x: cx - r + 6, y: cy - r + 6, width: 2 * (r - 6), height: 2 * (r - 6)))
        c.setStrokeColor(UIColor(white: 1, alpha: 0x22 / 255).cgColor)
        c.setLineWidth(5)
        c.strokeEllipse(in: CGRect(x: cx - r, y: cy - r, width: 2 * r, height: 2 * r))

        // Anillo con degradado que gira y cambia de largo: se dibuja en tramos de color creciente.
        let angle = (t * 300).truncatingRemainder(dividingBy: 360)
        let sweepLen = 200 + 80 * sin(t * 2.2)
        let segments = 48
        c.setLineCap(.butt)
        for i in 0..<segments {
            let f0 = CGFloat(i) / CGFloat(segments), f1 = CGFloat(i + 1) / CGFloat(segments)
            let a0 = (angle - sweepLen * (1 - f0)) * .pi / 180
            let a1 = (angle - sweepLen * (1 - f1)) * .pi / 180 + 0.01
            c.setStrokeColor(Self.ringColor(f1).cgColor)
            c.addArc(center: CGPoint(x: cx, y: cy), radius: r, startAngle: a0, endAngle: a1, clockwise: false)
            c.strokePath()
        }
        // Punta redondeada del anillo.
        let head = angle * .pi / 180
        c.setFillColor(Self.ringColor(1).cgColor)
        c.fillEllipse(in: CGRect(x: cx + r * cos(head) - 2.5, y: cy + r * sin(head) - 2.5, width: 5, height: 5))

        // Triángulo de play redondeado que respira.
        let s = r * (0.42 + 0.04 * pulse)
        let play = UIBezierPath()
        play.move(to: CGPoint(x: cx - s * 0.45, y: cy - s * 0.75))
        play.addLine(to: CGPoint(x: cx - s * 0.45, y: cy + s * 0.75))
        play.addLine(to: CGPoint(x: cx + s * 0.85, y: cy))
        play.close()
        play.lineJoinStyle = .round
        play.lineWidth = 4
        UIColor(red: 1, green: 0.93, blue: 0.91, alpha: 1).setFill()
        UIColor(red: 1, green: 0.93, blue: 0.91, alpha: 1).setStroke()
        play.fill()
        play.stroke()

        if splash {
            let para = NSMutableParagraphStyle()
            para.alignment = .center
            let attrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 22, weight: .light),
                .foregroundColor: UIColor(white: 1, alpha: (150 + 90 * pulse) / 255),
                .kern: 5.5,
                .paragraphStyle: para,
            ]
            ("EDUTUBE" as NSString).draw(in: CGRect(x: 0, y: cy + r + 36, width: w, height: 30), withAttributes: attrs)
        }
    }

    /// Degradado del anillo: transparente → rojo → coral claro en la punta.
    private static func ringColor(_ f: CGFloat) -> UIColor {
        func mix(_ a: (CGFloat, CGFloat, CGFloat, CGFloat), _ b: (CGFloat, CGFloat, CGFloat, CGFloat), _ k: CGFloat) -> UIColor {
            UIColor(red: a.0 + (b.0 - a.0) * k, green: a.1 + (b.1 - a.1) * k,
                    blue: a.2 + (b.2 - a.2) * k, alpha: a.3 + (b.3 - a.3) * k)
        }
        let clear: (CGFloat, CGFloat, CGFloat, CGFloat) = (1, 0.23, 0.19, 0)
        let half: (CGFloat, CGFloat, CGFloat, CGFloat) = (1, 0.23, 0.19, 0.53)
        let red: (CGFloat, CGFloat, CGFloat, CGFloat) = (1, 0.23, 0.19, 1)
        let tip: (CGFloat, CGFloat, CGFloat, CGFloat) = (1, 0.69, 0.6, 1)
        if f < 0.45 { return mix(clear, half, f / 0.45) }
        if f < 0.85 { return mix(half, red, (f - 0.45) / 0.4) }
        return mix(red, tip, (f - 0.85) / 0.15)
    }

    /// CADisplayLink retiene a su destino; esto evita que la vista nunca se libere.
    private final class WeakTarget: NSObject {
        weak var view: LoadingView?
        init(_ view: LoadingView) { self.view = view }
        @objc func tick() { view?.setNeedsDisplay() }
    }
}
