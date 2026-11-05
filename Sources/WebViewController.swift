import AVFoundation
import UIKit
import WebKit

final class WebViewController: UIViewController {
    static let defaultURL = "https://m.youtube.com"

    private enum Pref {
        static let url = "url"
        static let smooth = "smooth"
        static let background = "background"
    }

    private let prefs = UserDefaults.standard
    private var webView: WKWebView!
    private let loading = LoadingView()
    private let loadingBar = LoadingBar()
    private var splashDone = false
    private var codecInfo = ""
    private var bufferingWork: DispatchWorkItem?
    private let castButton = UIButton(type: .system)
    private var urlObserver: NSKeyValueObservation?

    private var homeURL: String { prefs.string(forKey: Pref.url) ?? Self.defaultURL }
    private var smooth: Bool { prefs.bool(forKey: Pref.smooth) }
    private var backgroundPlay: Bool { prefs.object(forKey: Pref.background) as? Bool ?? true }

    /// Google no deja iniciar sesión desde navegadores "incrustados"; nos presentamos como Safari.
    private static var safariUA: String {
        let os = UIDevice.current.systemVersion.replacingOccurrences(of: ".", with: "_")
        let parts = UIDevice.current.systemVersion.split(separator: ".")
        let version = parts.prefix(2).joined(separator: ".")
        let device = UIDevice.current.userInterfaceIdiom == .pad ? "iPad; CPU OS" : "iPhone; CPU iPhone OS"
        return "Mozilla/5.0 (\(device) \(os) like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
            + "Version/\(version) Mobile/15E148 Safari/604.1"
    }

    override var preferredStatusBarStyle: UIStatusBarStyle { .lightContent }
    override var prefersHomeIndicatorAutoHidden: Bool { true }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        setupWebView()
        setupCastButton()

        // Al cargar un video: barra delgada abajo en vez de la animación grande.
        loadingBar.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(loadingBar)
        NSLayoutConstraint.activate([
            loadingBar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            loadingBar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            loadingBar.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            loadingBar.heightAnchor.constraint(equalToConstant: 3),
        ])

        loading.frame = view.bounds
        loading.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        view.addSubview(loading)
        loading.show(splash: true)

        // Mantener con dos dedos: menú.
        let press = UILongPressGestureRecognizer(target: self, action: #selector(longPress(_:)))
        press.numberOfTouchesRequired = 2
        press.minimumPressDuration = 0.6
        webView.addGestureRecognizer(press)

        // Por si las reglas tardan: si en 8 s no están, carga igual.
        DispatchQueue.main.asyncAfter(deadline: .now() + 8) { [weak self] in self?.loadHomeIfNeeded() }
    }

    // MARK: - WebView

    private func setupWebView() {
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .default() // guarda la sesión iniciada
        config.allowsInlineMediaPlayback = true
        config.allowsPictureInPictureMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []
        config.defaultWebpagePreferences.preferredContentMode = .mobile
        config.preferences.javaScriptCanOpenWindowsAutomatically = false

        let ucc = config.userContentController
        ucc.add(WeakHandler(self), name: "tvweb")
        addScripts(to: ucc)

        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.customUserAgent = Self.safariUA
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.allowsBackForwardNavigationGestures = true // deslizar desde el borde = atrás
        webView.isOpaque = false
        webView.backgroundColor = .black
        webView.scrollView.backgroundColor = .black
        if #available(iOS 16.4, *) { webView.isInspectable = true }

        let refresh = UIRefreshControl()
        refresh.tintColor = .white
        refresh.addTarget(self, action: #selector(pullToRefresh(_:)), for: .valueChanged)
        webView.scrollView.refreshControl = refresh

        view.addSubview(webView)
        webView.translatesAutoresizingMaskIntoConstraints = false
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            webView.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            webView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
        ])

        // Las reglas de bloqueo se agregan a medida que se compilan; la primera (anuncios de video) tarda poco.
        AdBlocker.shared.onRuleList { [weak self] list in
            guard let self = self else { return }
            ucc.add(list)
            self.loadHomeIfNeeded()
        }
    }

    private func addScripts(to ucc: WKUserContentController) {
        ucc.removeAllUserScripts()
        let codec = Scripts.codec(smooth: smooth)
        codecInfo = codec.info
        NSLog("TVWeb: formato de video: %@", codecInfo)
        var sources = [codec.js, Scripts.youtube, Scripts.buffering, Scripts.cleanup]
        if backgroundPlay { sources.insert(Scripts.background, at: 0) }
        for src in sources {
            ucc.addUserScript(WKUserScript(source: src, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        }
        // Los videos de otras páginas suelen estar en reproductores incrustados: este va en todos los marcos.
        ucc.addUserScript(WKUserScript(source: Scripts.media, injectionTime: .atDocumentStart, forMainFrameOnly: false))
    }

    private var loadedOnce = false

    private func loadHomeIfNeeded() {
        guard !loadedOnce else { return }
        loadedOnce = true
        loadHome()
    }

    private func loadHome() {
        guard let url = URL(string: homeURL) else { return }
        webView.load(URLRequest(url: url))
    }

    @objc private func pullToRefresh(_ sender: UIRefreshControl) {
        webView.reload()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) { sender.endRefreshing() }
    }

    // MARK: - Transmitir a la TV

    private func setupCastButton() {
        let config = UIImage.SymbolConfiguration(pointSize: 20, weight: .semibold)
        castButton.setImage(UIImage(systemName: "tv", withConfiguration: config), for: .normal)
        castButton.tintColor = .white
        castButton.backgroundColor = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 0.92)
        castButton.layer.cornerRadius = 26
        castButton.layer.shadowColor = UIColor.black.cgColor
        castButton.layer.shadowOpacity = 0.4
        castButton.layer.shadowRadius = 6
        castButton.layer.shadowOffset = CGSize(width: 0, height: 2)
        castButton.accessibilityLabel = "Transmitir a la TV"
        castButton.addTarget(self, action: #selector(castTapped), for: .touchUpInside)
        castButton.addGestureRecognizer(UILongPressGestureRecognizer(target: self, action: #selector(castLongPress(_:))))
        castButton.isHidden = true
        castButton.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(castButton)
        NSLayoutConstraint.activate([
            castButton.widthAnchor.constraint(equalToConstant: 52),
            castButton.heightAnchor.constraint(equalToConstant: 52),
            castButton.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -16),
            castButton.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -72),
        ])
        // YouTube cambia de página sin recargar; se mira la URL para mostrar el botón solo en los videos.
        urlObserver = webView.observe(\.url, options: [.new]) { [weak self] _, _ in
            DispatchQueue.main.async { self?.updateCastButton() }
        }
    }

    // Videos encontrados en la página actual (que no sea YouTube), para enviarlos al Chromecast.
    private var pageMedia: [String] = []
    private var playingMedia: String?
    private var mediaTime: Double = 0
    private var mediaPage: String?

    private func updateCastButton() {
        // Al cambiar de página se olvidan los videos de la anterior.
        let page = webView.url.map { "\($0.host ?? "")\($0.path)" }
        if page != mediaPage {
            mediaPage = page
            pageMedia = []
            playingMedia = nil
            mediaTime = 0
        }
        castButton.isHidden = currentVideoId() == nil && pageMedia.isEmpty && XVideo.postId(webView.url) == nil
        // Empieza a buscar Chromecast apenas se abre un video, para tenerlos listos al tocar el botón.
        if !castButton.isHidden { Chromecast.shared.startDiscovery() }
    }

    /// Id del video abierto (youtube.com/watch?v=ID o /shorts/ID).
    private func currentVideoId() -> String? {
        guard let url = webView.url, url.host?.contains("youtube.com") == true else { return nil }
        if url.path.hasPrefix("/shorts/") {
            let id = url.path.dropFirst("/shorts/".count).split(separator: "/").first.map(String.init)
            return id?.isEmpty == false ? id : nil
        }
        guard url.path == "/watch" else { return nil }
        return URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "v" }?.value
    }

    @objc private func castTapped() {
        if currentVideoId() == nil {
            return castPageMedia()
        }
        Chromecast.shared.startDiscovery()
        if Chromecast.shared.devices.isEmpty {
            // Recién empezó a buscar: se da un momento para que aparezcan los Chromecast.
            toast("Buscando Chromecast en tu Wi-Fi…")
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in self?.showCastPicker() }
        } else {
            showCastPicker()
        }
    }

    private func showCastPicker() {
        guard presentedViewController == nil else { return }
        let devices = Chromecast.shared.devices
        let sheet = UIAlertController(
            title: "Transmitir a",
            message: devices.isEmpty ? "No encontré ningún Chromecast. Revisa que el iPhone y el Chromecast estén en el mismo Wi-Fi "
                + "y que edutube tenga permiso de \"Red local\" en Ajustes." : nil,
            preferredStyle: .actionSheet)
        for device in devices {
            sheet.addAction(UIAlertAction(title: device.name, style: .default) { _ in self.castToChromecast(device) })
        }
        if TVCast.shared.isPaired {
            let name = TVCast.shared.screenName ?? "TV"
            sheet.addAction(UIAlertAction(title: "\(name) (vinculada con código)", style: .default) { _ in
                self.castToPairedTV()
            })
        }
        sheet.addAction(UIAlertAction(title: "Vincular con código de TV…", style: .default) { _ in
            self.askPairing { [weak self] in self?.castToPairedTV() }
        })
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let pop = sheet.popoverPresentationController {
            pop.sourceView = castButton
            pop.sourceRect = castButton.bounds
        }
        present(sheet, animated: true)
    }

    // MARK: - Espejo de pantalla

    /// Duplica toda la pantalla del iPhone en el Chromecast (con unos segundos de retraso).
    private func startMirror() {
        guard ScreenMirror.extensionId != nil else { return showError("Falta el módulo de espejo en esta instalación.") }
        Chromecast.shared.startDiscovery()
        toast("Toca «Iniciar transmisión»")
        ScreenMirror.showSystemPicker(in: view)
        ScreenMirror.waitUntilLive { [weak self] ok in
            guard let self = self else { return }
            guard ok else { return }
            guard let ip = ScreenMirror.wifiAddress() else {
                return self.showError("El iPhone tiene que estar conectado al mismo Wi-Fi que el Chromecast.")
            }
            let media = Chromecast.Media(url: "http://\(ip):\(ScreenMirror.port)/live.m3u8",
                                         title: "Pantalla del iPhone", time: 0, live: true)
            let devices = Chromecast.shared.devices
            let sheet = UIAlertController(
                title: "Mostrar la pantalla en",
                message: devices.isEmpty ? "No encontré ningún Chromecast en tu Wi-Fi." : "Para terminar, toca el punto rojo arriba a la izquierda (o el Centro de control) y luego «Detener».",
                preferredStyle: .actionSheet)
            for device in devices {
                sheet.addAction(UIAlertAction(title: device.name, style: .default) { _ in
                    self.toast("Conectando con \(device.name)…")
                    Chromecast.shared.playMedia(media, on: device) { result in
                        switch result {
                        case .success: self.toast("Pantalla en \(device.name)")
                        case .failure(let e): self.showError(e.localizedDescription)
                        }
                    }
                })
            }
            sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
            if let pop = sheet.popoverPresentationController {
                pop.sourceView = self.view
                pop.sourceRect = CGRect(x: self.view.bounds.midX, y: self.view.bounds.midY, width: 1, height: 1)
                pop.permittedArrowDirections = []
            }
            self.present(sheet, animated: true)
        }
    }

    // MARK: - Videos de cualquier página

    fileprivate func mediaFound(_ url: String, current: Bool) {
        guard webView.url?.host?.contains("youtube.com") != true else { return }
        if current { playingMedia = url }
        if !pageMedia.contains(url) { pageMedia.append(url) }
        castButton.isHidden = false
    }

    fileprivate func mediaTimeUpdate(_ t: Double) {
        mediaTime = t
    }

    /// El mejor candidato: el que está sonando; si no, la lista HLS principal; si no, el último mp4.
    private func bestMedia() -> String? {
        if let p = playingMedia { return p }
        if let hls = pageMedia.first(where: { $0.lowercased().contains("m3u8") }) { return hls }
        return pageMedia.last
    }

    private func castPageMedia() {
        // En X se pide el mp4 del post: es más confiable que la lista de trozos que usa la página.
        if let id = XVideo.postId(webView.url) {
            toast("Buscando el video del post…")
            return XVideo.resolve(id) { [weak self] mp4 in
                guard let self = self else { return }
                if let mp4 = mp4 {
                    if !self.pageMedia.contains(mp4) { self.pageMedia.append(mp4) }
                    self.pickDevice(for: mp4)
                } else {
                    self.pickDevice(for: nil)
                }
            }
        }
        pickDevice(for: nil)
    }

    private func pickDevice(for preferred: String?) {
        guard let url = preferred ?? bestMedia() else {
            return toast("Dale play al video de la página y vuelve a tocar el botón")
        }
        Chromecast.shared.startDiscovery()
        let show = { [weak self] in
            guard let self = self, self.presentedViewController == nil else { return }
            let devices = Chromecast.shared.devices
            let sheet = UIAlertController(
                title: "Enviar este video a",
                message: devices.isEmpty ? "No encontré ningún Chromecast. Revisa que el iPhone y el Chromecast estén en el mismo Wi-Fi "
                    + "y que edutube tenga permiso de \"Red local\" en Ajustes." : nil,
                preferredStyle: .actionSheet)
            for device in devices {
                sheet.addAction(UIAlertAction(title: device.name, style: .default) { _ in self.castMedia(url, to: device) })
            }
            sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
            if let pop = sheet.popoverPresentationController {
                pop.sourceView = self.castButton
                pop.sourceRect = self.castButton.bounds
            }
            self.present(sheet, animated: true)
        }
        if Chromecast.shared.devices.isEmpty {
            toast("Buscando Chromecast en tu Wi-Fi…")
            DispatchQueue.main.asyncAfter(deadline: .now() + 2, execute: show)
        } else {
            show()
        }
    }

    private func castMedia(_ url: String, to device: Chromecast.Device) {
        castStarted()
        toast("Enviando a \(device.name)…")
        let title = webView.title?.isEmpty == false ? webView.title! : (webView.url?.host ?? "Video")
        let time = url == playingMedia ? mediaTime : 0
        Self.prepare(url, title: title, time: time) { media in
            Chromecast.shared.playMedia(media, on: device) { [weak self] result in
                guard let self = self else { return }
                if case .failure = result, url != self.pageMedia.last, let other = self.pageMedia.last, other != url {
                    // Si la TV no pudo con ese, se prueba con el otro video encontrado.
                    return Self.prepare(other, title: title, time: 0) { retry in
                        Chromecast.shared.playMedia(retry, on: device) { self.mediaCastFinished($0, device: device) }
                    }
                }
                self.mediaCastFinished(result, device: device)
            }
        }
    }

    /// Para listas HLS, revisa si los trozos son fMP4 (si no se avisa, el Chromecast no los reproduce).
    private static func prepare(_ url: String, title: String, time: Double, completion: @escaping (Chromecast.Media) -> Void) {
        var media = Chromecast.Media(url: url, title: title, time: time)
        guard url.lowercased().contains(".m3u8"), let address = URL(string: url) else { return completion(media) }
        func load(_ u: URL, depth: Int, done: @escaping (String?) -> Void) {
            URLSession.shared.dataTask(with: URLRequest(url: u, timeoutInterval: 5)) { data, _, _ in
                guard let text = data.flatMap({ String(data: $0, encoding: .utf8) }) else { return done(nil) }
                // Lista maestra: se revisa la primera calidad para ver de qué tipo son sus trozos.
                if depth == 0, text.contains("#EXT-X-STREAM-INF"),
                   let line = text.split(whereSeparator: \.isNewline).first(where: { !$0.hasPrefix("#") && !$0.trimmingCharacters(in: .whitespaces).isEmpty }),
                   let sub = URL(string: String(line).trimmingCharacters(in: .whitespaces), relativeTo: u) {
                    return load(sub.absoluteURL, depth: 1, done: done)
                }
                done(text)
            }.resume()
        }
        load(address, depth: 0) { text in
            if let t = text?.lowercased() {
                media.fmp4 = t.contains("#ext-x-map") || t.contains(".m4s") || t.contains(".mp4")
            }
            DispatchQueue.main.async { completion(media) }
        }
    }

    private func mediaCastFinished(_ result: Result<String, Error>, device: Chromecast.Device) {
        switch result {
        case .success:
            webView.pauseAllMediaPlayback(completionHandler: nil)
            castFinished(.success(device.name))
        case .failure(let error):
            castFinished(.failure(Chromecast.CastError.message(
                "\(error.localizedDescription) Algunas páginas protegen sus videos para que solo se vean dentro de su sitio.")))
        }
    }

    private func castToChromecast(_ device: Chromecast.Device) {
        guard let id = currentVideoId() else { return }
        castStarted()
        toast("Conectando con \(device.name)…")
        currentTime { [weak self] time in
            Chromecast.shared.openYouTube(on: device) { result in
                switch result {
                case .success(let screenId):
                    TVCast.shared.cast(videoId: id, at: time, screenId: screenId, name: device.name) { self?.castFinished($0) }
                case .failure(let error):
                    self?.castFinished(.failure(error))
                }
            }
        }
    }

    private func castToPairedTV() {
        guard let id = currentVideoId() else { return }
        castStarted()
        currentTime { [weak self] time in
            TVCast.shared.cast(videoId: id, at: time) { self?.castFinished($0) }
        }
    }

    private func currentTime(_ completion: @escaping (Double) -> Void) {
        webView.evaluateJavaScript("(function(){var v=document.querySelector('video');return v?v.currentTime:0;})()") { r, _ in
            completion((r as? NSNumber)?.doubleValue ?? 0)
        }
    }

    private func castStarted() {
        castButton.isEnabled = false
        castButton.alpha = 0.6
    }

    private func castFinished(_ result: Result<String, Error>) {
        castButton.isEnabled = true
        castButton.alpha = 1
        switch result {
        case .success(let name):
            webView.evaluateJavaScript("var v=document.querySelector('video');if(v)v.pause();")
            toast("Reproduciendo en \(name)")
        case .failure(let error):
            showError(error.localizedDescription)
        }
    }

    @objc private func castLongPress(_ g: UILongPressGestureRecognizer) {
        guard g.state == .began else { return }
        let name = TVCast.shared.screenName ?? "TV"
        let sheet = UIAlertController(title: TVCast.shared.isPaired ? "Vinculado con \(name)" : "Sin TV vinculada",
                                      message: nil, preferredStyle: .actionSheet)
        sheet.addAction(UIAlertAction(title: "Vincular otra TV", style: .default) { _ in self.askPairing(then: nil) })
        if TVCast.shared.isPaired {
            sheet.addAction(UIAlertAction(title: "Desvincular \(name)", style: .destructive) { _ in
                TVCast.shared.unpair()
                self.toast("TV desvinculada")
            })
        }
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let pop = sheet.popoverPresentationController {
            pop.sourceView = castButton
            pop.sourceRect = castButton.bounds
        }
        present(sheet, animated: true)
    }

    private func askPairing(then next: (() -> Void)?) {
        let alert = UIAlertController(
            title: "Vincular la TV",
            message: "En la TV abre YouTube (o TV Web) → Configuración → \"Vincular con código de TV\". "
                + "Escribe aquí el código que aparece. Solo se hace una vez.",
            preferredStyle: .alert)
        alert.addTextField { f in
            f.placeholder = "123 456 789 012"
            f.keyboardType = .numberPad
        }
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Vincular", style: .default) { _ in
            TVCast.shared.pair(code: alert.textFields?.first?.text ?? "") { [weak self] result in
                switch result {
                case .success(let name):
                    self?.toast("Vinculado con \(name)")
                    next?()
                case .failure(let error):
                    self?.showError(error.localizedDescription)
                }
            }
        })
        present(alert, animated: true)
    }

    private func showError(_ text: String) {
        let alert = UIAlertController(title: "No se pudo transmitir", message: text, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    // MARK: - Segundo plano

    func didEnterBackground() {
        guard backgroundPlay else { return }
        try? AVAudioSession.sharedInstance().setActive(true)
        webView.evaluateJavaScript("window.__tvwebBg=1;")
        // iOS pausa el video al salir de la app; lo retomamos enseguida para que siga el audio.
        for delay in [0.3, 1.0, 2.0] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
                self?.webView.evaluateJavaScript("window.__tvwebResume&&window.__tvwebResume();")
            }
        }
    }

    func willEnterForeground() {
        webView.evaluateJavaScript("window.__tvwebBg=0;")
    }

    // MARK: - Animación de carga

    fileprivate func buffering(_ on: Bool) {
        bufferingWork?.cancel()
        guard splashDone else { return }
        if on {
            let work = DispatchWorkItem { [weak self] in self?.loadingBar.show() }
            bufferingWork = work
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35, execute: work) // cargas breves no muestran nada
        } else {
            loadingBar.hide()
        }
    }

    // MARK: - Menú

    @objc private func longPress(_ g: UILongPressGestureRecognizer) {
        if g.state == .began { showMenu() }
    }

    override func motionEnded(_ motion: UIEvent.EventSubtype, with event: UIEvent?) {
        if motion == .motionShake { showMenu() } // agitar el teléfono también abre el menú
    }

    override var canBecomeFirstResponder: Bool { true }

    private func showMenu() {
        guard presentedViewController == nil else { return }
        let title = "edutube · \(codecInfo) · \(AdBlocker.shared.blockedCount) dominios bloqueados"
        let sheet = UIAlertController(title: title, message: nil, preferredStyle: .actionSheet)
        sheet.addAction(UIAlertAction(title: "Ir a la página fija", style: .default) { _ in self.loadHome() })
        sheet.addAction(UIAlertAction(title: "Recargar", style: .default) { _ in self.webView.reload() })
        sheet.addAction(UIAlertAction(title: "Ir a una página…", style: .default) { _ in self.askGo() })
        sheet.addAction(UIAlertAction(title: "Espejo de pantalla en la TV", style: .default) { _ in self.startMirror() })
        sheet.addAction(UIAlertAction(title: "Cambiar página fija", style: .default) { _ in self.askURL() })
        sheet.addAction(UIAlertAction(title: "Fijar la página actual", style: .default) { _ in
            self.prefs.set(self.webView.url?.absoluteString, forKey: Pref.url)
            self.toast("Página fijada")
        })
        sheet.addAction(UIAlertAction(title: "Seguir sonando en segundo plano: \(backgroundPlay ? "Sí" : "No")",
                                      style: .default) { _ in
            self.prefs.set(!self.backgroundPlay, forKey: Pref.background)
            self.reloadScripts()
        })
        sheet.addAction(UIAlertAction(title: "Máxima fluidez (H.264, 30 fps): \(smooth ? "Sí" : "No")",
                                      style: .default) { _ in
            self.prefs.set(!self.smooth, forKey: Pref.smooth)
            self.reloadScripts()
            self.toast(self.smooth ? "Máxima fluidez activada" : "Calidad automática")
        })
        sheet.addAction(UIAlertAction(title: TVCast.shared.isPaired
                                        ? "Transmitir: desvincular \(TVCast.shared.screenName ?? "TV")"
                                        : "Transmitir: vincular la TV", style: .default) { _ in
            if TVCast.shared.isPaired {
                TVCast.shared.unpair()
                self.toast("TV desvinculada")
            } else {
                self.askPairing(then: nil)
            }
        })
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let pop = sheet.popoverPresentationController { // iPad
            pop.sourceView = view
            pop.sourceRect = CGRect(x: view.bounds.midX, y: view.bounds.midY, width: 1, height: 1)
            pop.permittedArrowDirections = []
        }
        present(sheet, animated: true)
    }

    private func reloadScripts() {
        addScripts(to: webView.configuration.userContentController)
        webView.reload()
    }

    /// Abre cualquier página o búsqueda, sin cambiar la página fija.
    private func askGo() {
        let alert = UIAlertController(title: "Ir a una página", message: "Escribe un link o lo que quieras buscar.",
                                      preferredStyle: .alert)
        alert.addTextField { f in
            f.placeholder = "ejemplo.com o una búsqueda"
            f.keyboardType = .webSearch
            f.autocapitalizationType = .none
            f.autocorrectionType = .no
            f.clearButtonMode = .whileEditing
        }
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Ir", style: .default) { _ in
            let text = (alert.textFields?.first?.text ?? "").trimmingCharacters(in: .whitespaces)
            guard !text.isEmpty else { return }
            var url: URL?
            if text.hasPrefix("http://") || text.hasPrefix("https://") {
                url = URL(string: text)
            } else if !text.contains(" "), text.contains(".") {
                url = URL(string: "https://" + text)
            }
            if url == nil {
                var c = URLComponents(string: "https://www.google.com/search")!
                c.queryItems = [URLQueryItem(name: "q", value: text)]
                url = c.url
            }
            if let url = url { self.webView.load(URLRequest(url: url)) }
        })
        present(alert, animated: true)
    }

    private func askURL() {
        let alert = UIAlertController(title: "Página fija", message: nil, preferredStyle: .alert)
        alert.addTextField { f in
            f.text = self.homeURL
            f.keyboardType = .URL
            f.autocapitalizationType = .none
            f.autocorrectionType = .no
            f.clearButtonMode = .whileEditing
        }
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Guardar", style: .default) { _ in
            var url = (alert.textFields?.first?.text ?? "").trimmingCharacters(in: .whitespaces)
            guard !url.isEmpty else { return }
            if !url.hasPrefix("http://") && !url.hasPrefix("https://") { url = "https://" + url }
            self.prefs.set(url, forKey: Pref.url)
            self.loadHome()
        })
        present(alert, animated: true)
    }

    private func toast(_ text: String) {
        let label = PaddedLabel()
        label.text = text
        label.textColor = .white
        label.font = .systemFont(ofSize: 15, weight: .medium)
        label.backgroundColor = UIColor(white: 0.1, alpha: 0.9)
        label.layer.cornerRadius = 16
        label.clipsToBounds = true
        label.alpha = 0
        label.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            label.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -40),
        ])
        UIView.animate(withDuration: 0.2, animations: { label.alpha = 1 }) { _ in
            UIView.animate(withDuration: 0.3, delay: 1.6, options: [], animations: { label.alpha = 0 }) { _ in label.removeFromSuperview() }
        }
    }
}

// MARK: - Navegación

extension WebViewController: WKNavigationDelegate, WKUIDelegate {
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = action.request.url else { return decisionHandler(.cancel) }
        let scheme = url.scheme?.lowercased() ?? ""
        // Bloquea redirecciones a apps (youtube://, itms-apps://, intent:) y a dominios de anuncios.
        if scheme == "about" || scheme == "blob" || scheme == "data" { return decisionHandler(.allow) }
        if scheme != "http" && scheme != "https" { return decisionHandler(.cancel) }
        if AdBlocker.shared.isBlocked(url.host) { return decisionHandler(.cancel) }
        // "allow + 2" = permitir sin abrir la app oficial de YouTube por enlace universal (valor interno de WebKit).
        decisionHandler(WKNavigationActionPolicy(rawValue: WKNavigationActionPolicy.allow.rawValue + 2) ?? .allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if !splashDone {
            splashDone = true
            becomeFirstResponder()
            // Deja que YouTube dibuje su pantalla antes de quitar la animación de inicio.
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) { [weak self] in self?.loading.hide() }
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        finishSplashOnError()
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        finishSplashOnError()
    }

    private func finishSplashOnError() {
        if !splashDone {
            splashDone = true
            loading.hide()
        }
    }

    /// Si WebKit se cae por falta de memoria, recarga en vez de quedar en blanco.
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        webView.reload()
    }

    /// Sin ventanas emergentes: los enlaces "en pestaña nueva" se abren en la misma.
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if action.navigationType == .linkActivated, let url = action.request.url,
           !AdBlocker.shared.isBlocked(url.host) {
            webView.load(action.request)
        }
        return nil
    }
}

// MARK: - Mensajes desde la página

extension WebViewController: WKScriptMessageHandler {
    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? String else { return }
        if body == "buffering:1" { buffering(true) } else if body == "buffering:0" { buffering(false) }
        else if body.hasPrefix("media-current:") { mediaFound(String(body.dropFirst(14)), current: true) }
        else if body.hasPrefix("media:") { mediaFound(String(body.dropFirst(6)), current: false) }
        else if body.hasPrefix("mtime:"), let t = Double(body.dropFirst(6)) { mediaTimeUpdate(t) }
    }
}

/// WKUserContentController retiene a sus manejadores; esto evita un ciclo de memoria.
private final class WeakHandler: NSObject, WKScriptMessageHandler {
    weak var target: WKScriptMessageHandler?
    init(_ target: WKScriptMessageHandler) { self.target = target }
    func userContentController(_ ucc: WKUserContentController, didReceive message: WKScriptMessage) {
        target?.userContentController(ucc, didReceive: message)
    }
}

private final class PaddedLabel: UILabel {
    override func drawText(in rect: CGRect) {
        super.drawText(in: rect.inset(by: UIEdgeInsets(top: 8, left: 16, bottom: 8, right: 16)))
    }

    override var intrinsicContentSize: CGSize {
        let s = super.intrinsicContentSize
        return CGSize(width: s.width + 32, height: s.height + 16)
    }
}
