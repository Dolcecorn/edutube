import UIKit

/// Lo que está sonando en la TV, venga de YouTube (TVCast) o del reproductor del Chromecast (CastRemote).
enum Remote {
    enum Target { case youtube, media, lg }
    typealias Option = (name: String, selected: Bool, action: () -> Void)

    static var target: Target?

    static var isActive: Bool {
        switch target {
        case .youtube: return TVCast.shared.isControlling
        case .media: return CastRemote.shared.isControlling
        case .lg: return LGTV.shared.isControlling
        case nil: return false
        }
    }

    static var title: String {
        switch target {
        case .youtube: return TVCast.shared.title
        case .media: return CastRemote.shared.title
        case .lg: return LGTV.shared.title
        case nil: return ""
        }
    }

    static var deviceName: String {
        switch target {
        case .media: return CastRemote.shared.device?.name ?? "TV"
        case .lg: return LGTV.shared.current?.name ?? "TV LG"
        default: return TVCast.shared.screenName ?? "TV"
        }
    }

    /// La LG no informa el tiempo: sin barra; los botones de saltar retroceden/avanzan rápido.
    static var canSeek: Bool { target != .lg }

    static var isPlaying: Bool {
        switch target {
        case .youtube: return TVCast.shared.isPlaying
        case .lg: return LGTV.shared.isPlaying
        default: return CastRemote.shared.isPlaying
        }
    }

    static var position: Double {
        switch target {
        case .youtube: return TVCast.shared.currentPosition
        case .lg: return 0
        default: return CastRemote.shared.currentPosition
        }
    }

    static var duration: Double {
        switch target {
        case .youtube: return TVCast.shared.duration
        case .lg: return 0
        default: return CastRemote.shared.duration
        }
    }

    static var volume: Double {
        switch target {
        case .youtube: return TVCast.shared.volumeLevel
        case .lg: return LGTV.shared.volume
        default: return CastRemote.shared.volume
        }
    }

    static var isMuted: Bool {
        switch target {
        case .youtube: return TVCast.shared.isMuted
        case .lg: return LGTV.shared.isMuted
        default: return CastRemote.shared.isMuted
        }
    }

    static func togglePlay() {
        switch target {
        case .youtube: isPlaying ? TVCast.shared.pause() : TVCast.shared.play()
        case .lg: isPlaying ? LGTV.shared.pause() : LGTV.shared.play()
        default: isPlaying ? CastRemote.shared.pause() : CastRemote.shared.play()
        }
    }

    static func seek(to t: Double) {
        switch target {
        case .youtube: TVCast.shared.seek(to: t)
        case .lg: break
        default: CastRemote.shared.seek(to: t)
        }
    }

    /// Botones de atrasar/adelantar.
    static func skip(_ seconds: Double) {
        if target == .lg {
            seconds < 0 ? LGTV.shared.rewind() : LGTV.shared.fastForward()
        } else {
            seek(to: position + seconds)
        }
    }

    static func setVolume(_ v: Double) {
        switch target {
        case .youtube: TVCast.shared.setVolume(v)
        case .lg: LGTV.shared.setVolume(v)
        default: CastRemote.shared.setVolume(v)
        }
    }

    static func setMuted(_ on: Bool) {
        switch target {
        case .youtube: TVCast.shared.setMuted(on)
        case .lg: LGTV.shared.setMuted(on)
        default: CastRemote.shared.setMuted(on)
        }
    }

    static func stop() {
        switch target {
        case .youtube: TVCast.shared.stop()
        case .lg: LGTV.shared.stop()
        default: CastRemote.shared.stop()
        }
        target = nil
    }

    /// Opciones de subtítulos: (nombre, elegido, acción). La primera es "Desactivados".
    static func subtitleOptions() -> [Option] {
        switch target {
        case .youtube:
            let tv = TVCast.shared
            let off: Option = ("Desactivados", tv.activeSubtitle == nil, { tv.selectSubtitle(nil) })
            return [off] + tv.subtitleTracks.map { t -> Option in (t.name, tv.activeSubtitle == t.id, { tv.selectSubtitle(t.id) }) }
        case .media:
            let r = CastRemote.shared
            let on = r.subtitles.filter { r.activeTracks.contains($0.id) }
            let off: Option = ("Desactivados", on.isEmpty, { r.selectSubtitle(nil) })
            return [off] + r.subtitles.map { t -> Option in (t.name, r.activeTracks.contains(t.id), { r.selectSubtitle(t.id) }) }
        case .lg, nil:
            return []
        }
    }

    static func audioOptions() -> [Option] {
        switch target {
        case .youtube:
            let tv = TVCast.shared
            return tv.audioTracks.map { t -> Option in (t.name, tv.activeAudio == t.id, { tv.selectAudio(t.id) }) }
        case .media:
            let r = CastRemote.shared
            return r.audios.map { t -> Option in (t.name, r.activeTracks.contains(t.id), { r.selectAudio(t.id) }) }
        case .lg, nil:
            return []
        }
    }
}

/// Control remoto de la TV: pausa, adelantar/atrasar, barra de tiempo, volumen, subtítulos, audio y detener.
final class RemoteViewController: UIViewController {
    private let red = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 1)
    private let titleLabel = UILabel()
    private let deviceLabel = UILabel()
    private let playButton = UIButton(type: .system)
    private let slider = UISlider()
    private let elapsed = UILabel()
    private let remaining = UILabel()
    private let volume = UISlider()
    private let muteButton = UIButton(type: .system)
    private let subsButton = UIButton(type: .system)
    private let audioButton = UIButton(type: .system)
    private var timer: Timer?
    private var dragging = false

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = UIColor(white: 0.08, alpha: 1)
        overrideUserInterfaceStyle = .dark

        deviceLabel.font = .systemFont(ofSize: 13, weight: .semibold)
        deviceLabel.textColor = red
        deviceLabel.textAlignment = .center
        titleLabel.font = .systemFont(ofSize: 19, weight: .bold)
        titleLabel.textColor = .white
        titleLabel.numberOfLines = 2
        titleLabel.textAlignment = .center

        slider.minimumTrackTintColor = red
        slider.addTarget(self, action: #selector(sliderDown), for: .touchDown)
        slider.addTarget(self, action: #selector(sliderMoved), for: .valueChanged)
        slider.addTarget(self, action: #selector(sliderUp), for: [.touchUpInside, .touchUpOutside, .touchCancel])
        for l in [elapsed, remaining] {
            l.font = .monospacedDigitSystemFont(ofSize: 13, weight: .regular)
            l.textColor = .secondaryLabel
        }
        remaining.textAlignment = .right
        let times = UIStackView(arrangedSubviews: [elapsed, remaining])
        times.distribution = .fillEqually

        let big = UIImage.SymbolConfiguration(pointSize: 44, weight: .bold)
        let mid = UIImage.SymbolConfiguration(pointSize: 28, weight: .semibold)
        playButton.setPreferredSymbolConfiguration(big, forImageIn: .normal)
        playButton.tintColor = .white
        playButton.addTarget(self, action: #selector(togglePlay), for: .touchUpInside)
        playButton.accessibilityLabel = "Reproducir o pausar"
        func skip(_ symbol: String, _ seconds: Double, _ label: String) -> UIButton {
            let b = UIButton(type: .system)
            b.setImage(UIImage(systemName: symbol, withConfiguration: mid), for: .normal)
            b.tintColor = .white
            b.accessibilityLabel = label
            b.addAction(UIAction { [weak self] _ in Remote.skip(seconds); self?.refresh() }, for: .touchUpInside)
            return b
        }
        let controls = UIStackView(arrangedSubviews: [
            skip("gobackward.30", -30, "Atrasar 30 segundos"), skip("gobackward.10", -10, "Atrasar 10 segundos"),
            playButton,
            skip("goforward.10", 10, "Adelantar 10 segundos"), skip("goforward.30", 30, "Adelantar 30 segundos"),
        ])
        controls.distribution = .equalSpacing
        controls.alignment = .center

        muteButton.tintColor = .white
        muteButton.addAction(UIAction { [weak self] _ in Remote.setMuted(!Remote.isMuted); self?.refresh() }, for: .touchUpInside)
        volume.minimumTrackTintColor = .white
        volume.addAction(UIAction { [weak self] _ in Remote.setVolume(Double(self?.volume.value ?? 1)) }, for: .valueChanged)
        let loud = UIImageView(image: UIImage(systemName: "speaker.wave.3.fill"))
        loud.tintColor = .secondaryLabel
        let vol = UIStackView(arrangedSubviews: [muteButton, volume, loud])
        vol.spacing = 12
        vol.alignment = .center

        for (b, symbol, text, action) in [
            (subsButton, "captions.bubble", "Subtítulos", #selector(chooseSubs)),
            (audioButton, "waveform", "Audio", #selector(chooseAudio)),
        ] {
            b.setImage(UIImage(systemName: symbol), for: .normal)
            b.setTitle("  " + text, for: .normal)
            b.tintColor = .white
            b.titleLabel?.font = .systemFont(ofSize: 15, weight: .semibold)
            b.backgroundColor = UIColor(white: 1, alpha: 0.1)
            b.layer.cornerRadius = 12
            b.heightAnchor.constraint(equalToConstant: 46).isActive = true
            b.addTarget(self, action: action, for: .touchUpInside)
        }
        let options = UIStackView(arrangedSubviews: [subsButton, audioButton])
        options.spacing = 12
        options.distribution = .fillEqually

        let stop = UIButton(type: .system)
        stop.setTitle("Dejar de transmitir", for: .normal)
        stop.setTitleColor(red, for: .normal)
        stop.titleLabel?.font = .systemFont(ofSize: 15, weight: .semibold)
        stop.addAction(UIAction { [weak self] _ in Remote.stop(); self?.dismiss(animated: true) }, for: .touchUpInside)

        let stack = UIStackView(arrangedSubviews: [deviceLabel, titleLabel, slider, times, controls, vol, options, stop])
        stack.axis = .vertical
        stack.spacing = 18
        stack.setCustomSpacing(6, after: deviceLabel)
        stack.setCustomSpacing(2, after: slider)
        stack.setCustomSpacing(28, after: times)
        stack.setCustomSpacing(28, after: controls)
        stack.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 28),
            stack.leadingAnchor.constraint(equalTo: view.layoutMarginsGuide.leadingAnchor, constant: 8),
            stack.trailingAnchor.constraint(equalTo: view.layoutMarginsGuide.trailingAnchor, constant: -8),
        ])

        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.refresh() }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        timer?.invalidate()
    }

    private func refresh() {
        deviceLabel.text = "EN \(Remote.deviceName.uppercased())"
        titleLabel.text = Remote.title.isEmpty ? "Transmitiendo" : Remote.title
        let symbol = Remote.isPlaying ? "pause.circle.fill" : "play.circle.fill"
        playButton.setImage(UIImage(systemName: symbol), for: .normal)
        let d = Remote.duration
        slider.isEnabled = d > 0
        slider.isHidden = !Remote.canSeek
        if !Remote.canSeek {
            elapsed.text = "⏪ ⏩ = rápido"
            remaining.text = ""
        } else if d > 0 {
            slider.maximumValue = Float(d)
            if !dragging { slider.value = Float(Remote.position) }
            elapsed.text = Self.time(Double(slider.value))
            remaining.text = "-" + Self.time(max(0, d - Double(slider.value)))
        } else {
            slider.value = 0
            elapsed.text = Self.time(Remote.position)
            remaining.text = "EN VIVO"
        }
        muteButton.setImage(UIImage(systemName: Remote.isMuted ? "speaker.slash.fill" : "speaker.fill"), for: .normal)
        if !volume.isTracking { volume.value = Float(Remote.volume) }
        subsButton.alpha = Remote.subtitleOptions().count > 1 ? 1 : 0.45
        audioButton.alpha = Remote.audioOptions().count > 1 ? 1 : 0.45
        if !Remote.isActive, Remote.target == nil { dismiss(animated: true) }
    }

    private static func time(_ t: Double) -> String {
        let s = Int(max(0, t))
        return s >= 3600 ? String(format: "%d:%02d:%02d", s / 3600, s / 60 % 60, s % 60) : String(format: "%d:%02d", s / 60, s % 60)
    }

    @objc private func togglePlay() {
        Remote.togglePlay()
        refresh()
    }

    @objc private func sliderDown() { dragging = true }

    @objc private func sliderMoved() {
        elapsed.text = Self.time(Double(slider.value))
    }

    @objc private func sliderUp() {
        dragging = false
        Remote.seek(to: Double(slider.value))
    }

    @objc private func chooseSubs() {
        choose("Subtítulos", Remote.subtitleOptions(),
               empty: "Este video no trae subtítulos que se puedan elegir desde aquí.", from: subsButton)
    }

    @objc private func chooseAudio() {
        choose("Audio", Remote.audioOptions(), empty: "Este video trae un solo idioma de audio.", from: audioButton)
    }

    private func choose(_ title: String, _ options: [Remote.Option], empty: String, from source: UIView) {
        let empty = Remote.target == .lg
            ? "La TV LG no deja elegir \(title.lowercased()) desde el teléfono. Usa el control de la TV (botón de opciones mientras se ve el video)."
            : empty
        guard options.count > 1 else {
            let a = UIAlertController(title: title, message: empty, preferredStyle: .alert)
            a.addAction(UIAlertAction(title: "OK", style: .default))
            return present(a, animated: true)
        }
        let sheet = UIAlertController(title: title, message: nil, preferredStyle: .actionSheet)
        for (name, selected, action) in options {
            sheet.addAction(UIAlertAction(title: (selected ? "✓ " : "") + name, style: .default) { _ in action() })
        }
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let pop = sheet.popoverPresentationController {
            pop.sourceView = source
            pop.sourceRect = source.bounds
        }
        present(sheet, animated: true)
    }
}
