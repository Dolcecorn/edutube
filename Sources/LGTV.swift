import Foundation
import Network

/**
 Envía videos a TVs LG con webOS (por ejemplo la 32LF585B) por la misma conexión que usa la app
 oficial de LG: un WebSocket en el puerto 3000 de la TV ("SSAP"). La primera vez la TV pregunta en
 pantalla si se acepta a edutube; después queda emparejada.

 Lo que se puede hacer:
 - YouTube: abre la app de YouTube de la TV en ese video.
 - Pluto, páginas y canales: abre el reproductor de la TV con el video (mp4 o HLS).
 - Control remoto: reproducir, pausa, detener, retroceder/avanzar rápido y volumen.
 */
final class LGTV {
    static let shared = LGTV()

    struct Device: Hashable {
        let ip: String
        var name: String
    }

    enum LGError: LocalizedError {
        case offline, rejected, timeout, failed(String)
        var errorDescription: String? {
            switch self {
            case .offline: return "No se pudo conectar con la TV LG. Revisa que esté encendida y en el mismo Wi-Fi."
            case .rejected: return "La TV no aceptó a edutube. Vuelve a intentarlo y elige «Aceptar» con el control de la TV."
            case .timeout: return "La TV no respondió. Si aparece un aviso en la TV, acéptalo con el control y vuelve a intentarlo."
            case .failed(let s): return "La TV LG respondió: \(s)"
            }
        }
    }

    private let prefs = UserDefaults.standard
    private(set) var devices: [Device] = []
    var onChange: (() -> Void)?

    private var socket: URLSessionWebSocketTask?
    private var socketIP: String?
    private var registered = false
    private var waitingRegister: [(Result<Void, Error>) -> Void] = []
    private var pending: [String: (Result<[String: Any], Error>) -> Void] = [:]
    private var counter = 0
    private lazy var session = URLSession(configuration: .default)

    // Estado para el control remoto.
    private(set) var current: Device?
    private(set) var title = ""
    private(set) var isPlaying = false
    private(set) var volume: Double = 0.2
    private(set) var isMuted = false
    var isControlling: Bool { current != nil && registered }

    private init() {
        // TVs encontradas antes: aparecen enseguida, sin esperar la búsqueda.
        for ip in prefs.stringArray(forKey: "lg.known") ?? [] {
            devices.append(Device(ip: ip, name: prefs.string(forKey: "lg.name.\(ip)") ?? "TV LG"))
        }
    }

    // MARK: - Buscar

    private var scanning = false
    private var lastScan = Date.distantPast

    /**
     Busca TVs LG en el Wi-Fi probando el puerto 3000 de cada dirección de la red (iOS no deja a
     las apps instaladas por fuera de la App Store usar la búsqueda por multidifusión).
     */
    func discover(force: Bool = false) {
        guard !scanning, force || Date().timeIntervalSince(lastScan) > 60,
              let ip = ScreenMirror.wifiAddress() else { return }
        let parts = ip.split(separator: ".")
        guard parts.count == 4 else { return }
        scanning = true
        lastScan = Date()
        let prefix = parts.prefix(3).joined(separator: ".")
        let group = DispatchGroup()
        for n in 1...254 {
            let host = "\(prefix).\(n)"
            guard host != ip else { continue }
            group.enter()
            probe(host) { [weak self] open in
                if open { self?.found(host) }
                group.leave()
            }
        }
        group.notify(queue: .main) { [weak self] in self?.scanning = false }
    }

    /// Para cuando la búsqueda no la encuentra: la IP se ve en la TV en Ajustes → Red → Conexión Wi-Fi → Avanzado.
    func add(ip: String) {
        found(ip.trimmingCharacters(in: .whitespaces))
    }

    private func probe(_ host: String, completion: @escaping (Bool) -> Void) {
        let conn = NWConnection(host: NWEndpoint.Host(host), port: 3000, using: .tcp)
        var done = false
        func finish(_ ok: Bool) {
            guard !done else { return }
            done = true
            conn.cancel()
            completion(ok)
        }
        conn.stateUpdateHandler = { state in
            switch state {
            case .ready: finish(true)
            case .failed, .waiting: finish(false)
            default: break
            }
        }
        conn.start(queue: .main)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { finish(false) }
    }

    private func found(_ ip: String) {
        guard !devices.contains(where: { $0.ip == ip }) else { return }
        devices.append(Device(ip: ip, name: prefs.string(forKey: "lg.name.\(ip)") ?? "TV LG"))
        var known = prefs.stringArray(forKey: "lg.known") ?? []
        if !known.contains(ip) { known.append(ip); prefs.set(known, forKey: "lg.known") }
        onChange?()
    }

    func forget(_ device: Device) {
        devices.removeAll { $0.ip == device.ip }
        prefs.set((prefs.stringArray(forKey: "lg.known") ?? []).filter { $0 != device.ip }, forKey: "lg.known")
        prefs.removeObject(forKey: "lg.key.\(device.ip)")
        if socketIP == device.ip { close() }
        onChange?()
    }

    // MARK: - Enviar

    /// Abre un video de YouTube en la app de YouTube de la TV.
    func playYouTube(_ videoId: String, title: String, on device: Device, completion: @escaping (Result<Void, Error>) -> Void) {
        request("ssap://system.launcher/launch", on: device, payload: [
            "id": "youtube.leanback.v4",
            "params": ["contentTarget": "https://www.youtube.com/tv?v=\(videoId)"],
        ]) { [weak self] result in
            if case .success = result { self?.started(device, title: title) }
            completion(result.map { _ in () })
        }
    }

    /// Abre un video (mp4 o lista HLS) en el reproductor de la TV.
    func playMedia(_ media: Chromecast.Media, on device: Device, completion: @escaping (Result<Void, Error>) -> Void) {
        request("ssap://media.viewer/open", on: device, payload: [
            "target": media.url, "title": media.title, "description": "", "mimeType": media.contentType,
            "iconSrc": "", "loop": false,
        ]) { [weak self] result in
            if case .success = result { self?.started(device, title: media.title) }
            completion(result.map { _ in () })
        }
    }

    private func started(_ device: Device, title: String) {
        current = device
        self.title = title
        isPlaying = true
        refreshVolume()
        onChange?()
    }

    // MARK: - Control remoto

    func play() { control("play"); isPlaying = true; onChange?() }
    func pause() { control("pause"); isPlaying = false; onChange?() }
    func rewind() { control("rewind") }
    func fastForward() { control("fastForward") }

    func stop() {
        control("stop")
        current = nil
        onChange?()
    }

    func setVolume(_ level: Double) {
        volume = max(0, min(1, level))
        guard let d = current else { return }
        request("ssap://audio/setVolume", on: d, payload: ["volume": Int((volume * 100).rounded())]) { _ in }
    }

    func setMuted(_ on: Bool) {
        isMuted = on
        guard let d = current else { return }
        request("ssap://audio/setMute", on: d, payload: ["mute": on]) { _ in }
        onChange?()
    }

    private func control(_ name: String) {
        guard let d = current else { return }
        request("ssap://media.controls/\(name)", on: d, payload: [:]) { _ in }
    }

    private func refreshVolume() {
        guard let d = current else { return }
        request("ssap://audio/getVolume", on: d, payload: [:]) { [weak self] result in
            guard case .success(let p) = result, let self = self else { return }
            // webOS 2 responde {volume, muted}; las más nuevas lo traen dentro de volumeStatus.
            let status = p["volumeStatus"] as? [String: Any] ?? p
            if let v = (status["volume"] as? NSNumber)?.doubleValue { self.volume = v / 100 }
            if let m = (status["muted"] as? Bool) ?? (status["muteStatus"] as? Bool) { self.isMuted = m }
            self.onChange?()
        }
    }

    // MARK: - Conexión

    private func request(_ uri: String, on device: Device, payload: [String: Any],
                         completion: @escaping (Result<[String: Any], Error>) -> Void) {
        connect(device) { [weak self] result in
            guard let self = self else { return }
            if case .failure(let e) = result { return completion(.failure(e)) }
            self.counter += 1
            let id = "req\(self.counter)"
            self.pending[id] = completion
            self.send(["type": "request", "id": id, "uri": uri, "payload": payload])
            DispatchQueue.main.asyncAfter(deadline: .now() + 10) { [weak self] in
                self?.pending.removeValue(forKey: id)?(.failure(LGError.timeout))
            }
        }
    }

    private func connect(_ device: Device, completion: @escaping (Result<Void, Error>) -> Void) {
        if socketIP == device.ip, socket != nil {
            if registered { return completion(.success(())) }
            waitingRegister.append(completion)
            return
        }
        close()
        guard let url = URL(string: "ws://\(device.ip):3000") else { return completion(.failure(LGError.offline)) }
        let ws = session.webSocketTask(with: url)
        socket = ws
        socketIP = device.ip
        registered = false
        waitingRegister = [completion]
        ws.resume()
        listen(ws)
        var payload: [String: Any] = ["forcePairing": false, "pairingType": "PROMPT", "manifest": Self.manifest]
        if let key = prefs.string(forKey: "lg.key.\(device.ip)") { payload["client-key"] = key }
        send(["type": "register", "id": "register0", "payload": payload])
        // La primera vez hay que aceptar el aviso en la TV: se le da tiempo.
        DispatchQueue.main.asyncAfter(deadline: .now() + 60) { [weak self] in
            guard let self = self, self.socket === ws, !self.registered else { return }
            self.failRegister(LGError.timeout)
        }
    }

    private func close() {
        socket?.cancel(with: .goingAway, reason: nil)
        socket = nil
        socketIP = nil
        registered = false
        let waiting = pending
        pending = [:]
        waiting.values.forEach { $0(.failure(LGError.offline)) }
    }

    private func failRegister(_ error: Error) {
        let waiting = waitingRegister
        waitingRegister = []
        close()
        waiting.forEach { $0(.failure(error)) }
    }

    private func send(_ message: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: message),
              let text = String(data: data, encoding: .utf8) else { return }
        socket?.send(.string(text)) { _ in }
    }

    private func listen(_ ws: URLSessionWebSocketTask) {
        ws.receive { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self, self.socket === ws else { return }
                switch result {
                case .failure:
                    if !self.registered { self.failRegister(LGError.offline) } else { self.close() }
                case .success(let message):
                    if case .string(let text) = message { self.handle(text) }
                    self.listen(ws)
                }
            }
        }
    }

    private func handle(_ text: String) {
        guard let json = (try? JSONSerialization.jsonObject(with: Data(text.utf8))) as? [String: Any] else { return }
        let type = json["type"] as? String ?? ""
        let id = json["id"] as? String ?? ""
        let payload = json["payload"] as? [String: Any] ?? [:]
        if id == "register0" {
            switch type {
            case "registered":
                if let key = payload["client-key"] as? String, let ip = socketIP {
                    prefs.set(key, forKey: "lg.key.\(ip)")
                }
                registered = true
                let waiting = waitingRegister
                waitingRegister = []
                waiting.forEach { $0(.success(())) }
            case "error":
                failRegister(LGError.rejected)
            default:
                break // "response" con pairingType PROMPT: la TV está mostrando el aviso
            }
            return
        }
        guard let done = pending.removeValue(forKey: id) else { return }
        if type == "error" || (payload["returnValue"] as? Bool) == false {
            let reason = json["error"] as? String ?? payload["errorText"] as? String ?? "error"
            done(.failure(LGError.failed(reason)))
        } else {
            done(.success(payload))
        }
    }

    /// Permisos que se piden a la TV (los mismos que piden las apps de control remoto conocidas).
    private static let manifest: [String: Any] = [
        "manifestVersion": 1,
        "appVersion": "1.1",
        "permissions": [
            "LAUNCH", "LAUNCH_WEBAPP", "APP_TO_APP", "CLOSE", "TEST_OPEN", "TEST_PROTECTED",
            "CONTROL_AUDIO", "CONTROL_DISPLAY", "CONTROL_INPUT_JOYSTICK", "CONTROL_INPUT_MEDIA_RECORDING",
            "CONTROL_INPUT_MEDIA_PLAYBACK", "CONTROL_INPUT_TV", "CONTROL_POWER", "READ_APP_STATUS",
            "READ_CURRENT_CHANNEL", "READ_INPUT_DEVICE_LIST", "READ_NETWORK_STATE", "READ_RUNNING_APPS",
            "READ_TV_CHANNEL_LIST", "WRITE_NOTIFICATION_TOAST", "READ_POWER_STATE", "READ_COUNTRY_INFO",
            "READ_INSTALLED_APPS", "CONTROL_MOUSE_AND_KEYBOARD",
        ],
    ]
}
