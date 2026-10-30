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

    private func updateCastButton() {
        castButton.isHidden = currentVideoId() == nil
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
        guard let id = currentVideoId() else { return toast("Abre un video para enviarlo a la TV") }
        guard TVCast.shared.isPaired else {
            return askPairing { [weak self] in self?.castTapped() }
        }
        castButton.isEnabled = false
        castButton.alpha = 0.6
        webView.evaluateJavaScript("(function(){var v=document.querySelector('video');return v?v.currentTime:0;})()") { [weak self] r, _ in
            let time = (r as? NSNumber)?.doubleValue ?? 0
            TVCast.shared.cast(videoId: id, at: time) { result in
                guard let self = self else { return }
                self.castButton.isEnabled = true
                self.castButton.alpha = 1
                switch result {
                case .success(let name):
                    self.webView.evaluateJavaScript("var v=document.querySelector('video');if(v)v.pause();")
                    self.toast("Reproduciendo en \(name)")
                case .failure(let error):
                    self.showError(error.localizedDescription)
                }
            }
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
            let work = DispatchWorkItem { [weak self] in self?.loading.show(splash: false) }
            bufferingWork = work
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35, execute: work) // cargas breves no muestran nada
        } else {
            loading.hide()
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
