import AVFoundation
import Foundation

/**
 Envía videos a una TV con YouTube usando "Vincular con código de TV" (la API "lounge" de YouTube),
 la misma que usa la app oficial. Sirve con la app TV Web de la TV, con la app de YouTube de la TV
 y con Chromecast. Solo hay que vincular una vez con el código que muestra la TV.
 */
final class TVCast {
    static let shared = TVCast()

    private static let api = "https://www.youtube.com/api/lounge"
    private let prefs = UserDefaults.standard
    private let session = URLSession(configuration: .ephemeral)

    private var loungeToken: String?
    private var sid: String?
    private var gsession: String?
    private var lastEventId: String?
    private var offset = 1
    /// Pantalla con la que está abierta la sesión (la TV vinculada por código o un Chromecast).
    private var activeScreen: String?

    var screenName: String? { prefs.string(forKey: "cast.name") }
    var isPaired: Bool { prefs.string(forKey: "cast.screen") != nil }

    private var screenId: String? {
        get { prefs.string(forKey: "cast.screen") }
        set { prefs.set(newValue, forKey: "cast.screen") }
    }

    private var deviceId: String {
        if let id = prefs.string(forKey: "cast.device") { return id }
        let id = UUID().uuidString.lowercased()
        prefs.set(id, forKey: "cast.device")
        return id
    }

    enum CastError: LocalizedError {
        case badCode, notPaired, offline, failed(String)
        var errorDescription: String? {
            switch self {
            case .badCode: return "El código no es válido o ya expiró. Pide uno nuevo en la TV."
            case .notPaired: return "Primero vincula la TV."
            case .offline: return "No se pudo conectar con la TV. Revisa que tenga YouTube abierto."
            case .failed(let s): return s
            }
        }
    }

    // MARK: - Vincular

    /// Vincula con el código de 12 dígitos que muestra la TV en Ajustes → "Vincular con código de TV".
    func pair(code: String, completion: @escaping (Result<String, Error>) -> Void) {
        let digits = code.filter(\.isNumber)
        guard digits.count >= 9 else { return done(completion, .failure(CastError.badCode)) }
        post("/pairing/get_screen", form: ["pairing_code": digits]) { data, _ in
            guard let json = data.flatMap({ try? JSONSerialization.jsonObject(with: $0) }) as? [String: Any],
                  let screen = json["screen"] as? [String: Any],
                  let id = screen["screenId"] as? String,
                  let token = screen["loungeToken"] as? String else {
                return self.done(completion, .failure(CastError.badCode))
            }
            let name = screen["name"] as? String ?? "TV"
            self.screenId = id
            self.prefs.set(name, forKey: "cast.name")
            self.activeScreen = id
            self.loungeToken = token
            self.resetSession()
            self.done(completion, .success(name))
        }
    }

    func unpair() {
        if activeScreen == screenId { activeScreen = nil }
        prefs.removeObject(forKey: "cast.screen")
        prefs.removeObject(forKey: "cast.name")
        loungeToken = nil
        resetSession()
    }

    // MARK: - Enviar

    /// Reproduce el video en la TV desde el segundo indicado.
    func cast(videoId: String, at time: Double, completion: @escaping (Result<String, Error>) -> Void) {
        guard let id = screenId else { return done(completion, .failure(CastError.notPaired)) }
        cast(videoId: videoId, at: time, screenId: id, name: screenName ?? "TV", completion: completion)
    }

    /// Igual, pero a una pantalla concreta (por ejemplo, la de un Chromecast recién encontrado).
    func cast(videoId: String, at time: Double, screenId: String, name: String,
              completion: @escaping (Result<String, Error>) -> Void) {
        if activeScreen != screenId {
            activeScreen = screenId
            loungeToken = nil
            resetSession()
        }
        currentVideo = videoId
        position = (time, Date())
        playing = true
        inAd = false
        lastReload = Date() // el anuncio inicial de un video recién enviado no se recarga
        enqueue("setPlaylist", params: Self.playlist(videoId, at: time)) { result in
            if case .success = result { self.startWatchingAds() }
            self.done(completion, result.map { _ in name })
        }
    }

    private static func playlist(_ videoId: String, at time: Double) -> [String: String] {
        ["videoId": videoId, "currentTime": time < 1 ? "0" : String(Int(time)), "currentIndex": "0",
         "videoIds": videoId, "listId": "", "audioOnly": "false", "params": "", "playerParams": ""]
    }

    // MARK: - Anuncios en la TV

    /*
     Cuando el video se reproduce en el Chromecast, es el Chromecast el que pide los anuncios a YouTube,
     así que los bloqueos del iPhone no le llegan. Lo que sí se puede hacer (igual que iSponsorBlockTV) es
     quedarse escuchando a la TV: cuando avisa que empezó un anuncio se silencia, y apenas YouTube
     permite "Omitir", se omite. Funciona mientras edutube siga abierto o en segundo plano.
     */

    private var watching = false
    private var watchTask: URLSessionDataTask?
    private var watchStatus = 0
    private var stream = [UInt8]()
    private var watchFailures = 0
    private var watchStarted = Date()
    private var volume = "100"
    private var mutedByUs = false

    // Lo que se está viendo en la TV, para poder volver a cargarlo justo donde iba.
    private var currentVideo: String?
    private var position: (time: Double, at: Date)?
    private var playing = false
    private var inAd = false
    private var lastReload = Date.distantPast
    private lazy var streamSession = URLSession(configuration: .default, delegate: StreamDelegate(self), delegateQueue: .main)
    private let keepAlive = KeepAlive()

    private func startWatchingAds() {
        if !watching {
            watching = true
            watchStarted = Date()
            watchFailures = 0
            keepAlive.start()
        }
        if watchTask == nil { subscribe() }
    }

    private func stopWatchingAds() {
        watching = false
        watchTask?.cancel()
        watchTask = nil
        keepAlive.stop()
    }

    private func subscribe() {
        guard watching else { return }
        // Pasadas 4 horas sin parar, se deja de escuchar.
        if Date().timeIntervalSince(watchStarted) > 4 * 3600 { return stopWatchingAds() }
        guard let token = loungeToken, let sid = sid, let gs = gsession else { return resubscribeLater() }
        var query = [
            "name": "iPhone (edutube)", "loungeIdToken": token, "SID": sid, "gsessionid": gs,
            "device": "REMOTE_CONTROL", "app": "youtube-desktop", "VER": "8", "v": "2",
            "RID": "rpc", "CI": "0", "TYPE": "xmlhttp",
        ]
        if let aid = lastEventId { query["AID"] = aid }
        var comps = URLComponents(string: Self.api + "/bc/bind")!
        comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        var req = URLRequest(url: comps.url!, timeoutInterval: 600)
        req.httpMethod = "GET"
        stream.removeAll()
        watchStatus = 0
        let task = streamSession.dataTask(with: req)
        watchTask = task
        task.resume()
    }

    fileprivate func streamResponse(_ status: Int) {
        watchStatus = status
    }

    fileprivate func streamData(_ data: Data) {
        stream.append(contentsOf: data)
        parseStream()
    }

    fileprivate func streamEnded(_ task: URLSessionTask, error: Error?) {
        guard task === watchTask else { return }
        watchTask = nil
        guard watching else { return }
        if watchStatus == 200 && error == nil {
            watchFailures = 0
            subscribe() // la conexión larga se corta sola cada tanto; se abre otra
            return
        }
        resetSession()
        if watchStatus == 401 { loungeToken = nil }
        resubscribeLater()
    }

    private func resubscribeLater() {
        watchFailures += 1
        guard watchFailures <= 8 else { return stopWatchingAds() }
        DispatchQueue.main.asyncAfter(deadline: .now() + Double(min(watchFailures * 2, 15))) {
            guard self.watching, self.watchTask == nil else { return }
            self.ensureConnected { ok in ok ? self.subscribe() : self.resubscribeLater() }
        }
    }

    /// El flujo trae bloques "largo\n[[id,["evento",{...}]],...]". Se busca el fin de cada arreglo JSON.
    private func parseStream() {
        while true {
            guard let newline = stream.firstIndex(of: 0x0A) else { return }
            let start = newline + 1
            guard start < stream.count else { return }
            guard stream[start] == UInt8(ascii: "[") else {
                stream.removeFirst(start) // línea con el largo del bloque
                continue
            }
            var depth = 0, inString = false, escaped = false, end: Int?
            var i = start
            while i < stream.count {
                let c = stream[i]
                if inString {
                    if escaped { escaped = false } else if c == UInt8(ascii: "\\") { escaped = true } else if c == UInt8(ascii: "\"") { inString = false }
                } else if c == UInt8(ascii: "\"") {
                    inString = true
                } else if c == UInt8(ascii: "[") {
                    depth += 1
                } else if c == UInt8(ascii: "]") {
                    depth -= 1
                    if depth == 0 { end = i; break }
                }
                i += 1
            }
            guard let last = end else { return }
            let chunk = Data(stream[start...last])
            stream.removeFirst(last + 1)
            if let events = (try? JSONSerialization.jsonObject(with: chunk)) as? [[Any]] {
                for event in events { handle(event) }
            }
        }
    }

    private func handle(_ event: [Any]) {
        guard event.count == 2, let body = event[1] as? [Any], let type = body.first as? String else { return }
        if let id = event[0] as? NSNumber { lastEventId = id.stringValue }
        let data = body.count > 1 ? body[1] as? [String: Any] : nil
        let str = { (key: String) in data?[key] as? String ?? "" }
        switch type {
        case "onAdStateChange", "adPlaying":
            if !str("contentVideoId").isEmpty { currentVideo = str("contentVideoId") }
            if type == "onAdStateChange" && str("adState") == "0" && str("currentTime") != "0" {
                inAd = false
                mute(false) // terminó el anuncio
                return
            }
            let starting = !inAd
            inAd = true
            if starting && reloadPastAd() {
                mute(true) // mientras recarga, sin sonido
            } else if str("isSkipEnabled") == "true" {
                enqueue("skipAd", params: [:]) { _ in }
                mute(false)
            } else {
                mute(true) // anuncio que aún no se puede omitir: sin sonido
            }
        case "onStateChange", "nowPlaying":
            if !str("videoId").isEmpty { currentVideo = str("videoId") }
            let state = str("state")
            if state == "1" { inAd = false; mute(false) }
            // Durante un anuncio estos avisos traen el tiempo del anuncio, no el del video.
            if !inAd, let t = Double(str("currentTime")) { position = (t, Date()) }
            if !inAd, !state.isEmpty { playing = state == "1" }
        case "onVolumeChanged":
            if !mutedByUs, !str("volume").isEmpty { volume = str("volume") }
        case "loungeScreenDisconnected":
            stopWatchingAds()
            resetSession()
        default:
            break
        }
    }

    /**
     Anuncio a mitad del video: en vez de esperarlo, se vuelve a cargar el mismo video un segundo
     después de donde iba, que suele saltarse esa pausa publicitaria. Si YouTube insiste y vuelve a
     poner el anuncio enseguida, no se repite (se silencia y se omite como antes).
     */
    private func reloadPastAd() -> Bool {
        guard let video = currentVideo, let pos = position else { return false }
        let now = pos.time + (playing ? Date().timeIntervalSince(pos.at) : 0)
        guard now > 5, Date().timeIntervalSince(lastReload) > 30 else { return false }
        lastReload = Date()
        position = (now + 1, Date())
        inAd = false
        enqueue("setPlaylist", params: Self.playlist(video, at: now + 1)) { _ in }
        return true
    }

    private func mute(_ on: Bool) {
        guard on != mutedByUs else { return }
        mutedByUs = on
        enqueue("setVolume", params: ["volume": volume, "muted": on ? "true" : "false"]) { _ in }
    }

    // MARK: - Cola de comandos (uno a la vez, para que la numeración no se desordene)

    private var pending: [() -> Void] = []
    private var busy = false

    private func enqueue(_ name: String, params: [String: String], completion: @escaping (Result<Void, Error>) -> Void) {
        pending.append {
            self.command(name, params: params, retry: true) { result in
                completion(result)
                self.busy = false
                self.runNext()
            }
        }
        runNext()
    }

    private func runNext() {
        guard !busy, !pending.isEmpty else { return }
        busy = true
        pending.removeFirst()()
    }

    // MARK: - Protocolo

    private func command(_ name: String, params: [String: String], retry: Bool,
                         completion: @escaping (Result<Void, Error>) -> Void) {
        ensureConnected { ok in
            guard ok, let token = self.loungeToken, let sid = self.sid, let gs = self.gsession else {
                return completion(.failure(CastError.offline))
            }
            // Igual que pyytlounge: ofs parte en 1 y RID va un paso adelante.
            var body = ["count": "1", "ofs": String(self.offset), "req0__sc": name]
            for (k, v) in params { body["req0_\(k)"] = v }
            self.offset += 1
            var query = [
                "name": "iPhone (edutube)", "loungeIdToken": token, "SID": sid, "gsessionid": gs,
                "device": "REMOTE_CONTROL", "app": "youtube-desktop", "VER": "8", "v": "2", "RID": String(self.offset),
            ]
            if let aid = self.lastEventId { query["AID"] = aid }
            self.post("/bc/bind", query: query, form: body) { data, status in
                if status == 200 { return completion(.success(())) }
                // Sesión vencida: reconecta una vez y reintenta.
                self.resetSession()
                if status == 401 { self.loungeToken = nil }
                if retry {
                    self.command(name, params: params, retry: false, completion: completion)
                } else {
                    let text = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
                    completion(.failure(CastError.failed("La TV respondió \(status). \(text.prefix(80))")))
                }
            }
        }
    }

    private func ensureConnected(_ completion: @escaping (Bool) -> Void) {
        if sid != nil, gsession != nil, loungeToken != nil { return completion(true) }
        refreshToken { ok in
            guard ok, let token = self.loungeToken else { return completion(false) }
            let body = [
                "app": "web", "mdx-version": "3", "name": "iPhone (edutube)", "id": self.deviceId,
                "device": "REMOTE_CONTROL", "capabilities": "que,dsdtr,atp,vsp", "magnaKey": "cloudPairedDevice",
                "ui": "false", "theme": "cl", "loungeIdToken": token,
                "deviceContext": "user_agent=TVWeb&window_width_points=&window_height_points=&os_name=ios&ms=",
            ]
            let query = ["RID": "1", "VER": "8", "CVER": "1", "auth_failure_option": "send_error"]
            self.post("/bc/bind", query: query, form: body) { data, status in
                guard status == 200, let text = data.flatMap({ String(data: $0, encoding: .utf8) }) else {
                    if status == 401 { self.loungeToken = nil }
                    return completion(false)
                }
                self.sid = Self.first(#"\["c","([^"]+)""#, in: text)
                self.gsession = Self.first(#"\["S","([^"]+)""#, in: text)
                self.lastEventId = Self.last(#"\[(\d+),\["#, in: text)
                self.offset = 1
                completion(self.sid != nil && self.gsession != nil)
            }
        }
    }

    private func refreshToken(_ completion: @escaping (Bool) -> Void) {
        if loungeToken != nil { return completion(true) }
        guard let id = activeScreen else { return completion(false) }
        post("/pairing/get_lounge_token_batch", form: ["screen_ids": id]) { data, _ in
            guard let json = data.flatMap({ try? JSONSerialization.jsonObject(with: $0) }) as? [String: Any],
                  let screen = (json["screens"] as? [[String: Any]])?.first,
                  let token = screen["loungeToken"] as? String else { return completion(false) }
            self.loungeToken = token
            completion(true)
        }
    }

    private func resetSession() {
        sid = nil
        gsession = nil
        lastEventId = nil
    }

    private func post(_ path: String, query: [String: String] = [:], form: [String: String],
                      completion: @escaping (Data?, Int) -> Void) {
        var comps = URLComponents(string: Self.api + path)!
        if !query.isEmpty { comps.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) } }
        var req = URLRequest(url: comps.url!, timeoutInterval: 15)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = Self.encode(form).data(using: .utf8)
        session.dataTask(with: req) { data, resp, _ in
            let status = (resp as? HTTPURLResponse)?.statusCode ?? 0
            DispatchQueue.main.async { completion(data, status) }
        }.resume()
    }

    private func done<T>(_ completion: @escaping (Result<T, Error>) -> Void, _ result: Result<T, Error>) {
        DispatchQueue.main.async { completion(result) }
    }

    private static func encode(_ form: [String: String]) -> String {
        var allowed = CharacterSet.alphanumerics
        allowed.insert(charactersIn: "-._~")
        return form.map { k, v in
            "\(k.addingPercentEncoding(withAllowedCharacters: allowed) ?? k)="
                + (v.addingPercentEncoding(withAllowedCharacters: allowed) ?? v)
        }.joined(separator: "&")
    }

    private static func first(_ pattern: String, in text: String) -> String? {
        matches(pattern, in: text).first
    }

    private static func last(_ pattern: String, in text: String) -> String? {
        matches(pattern, in: text).last
    }

    private static func matches(_ pattern: String, in text: String) -> [String] {
        guard let rx = try? NSRegularExpression(pattern: pattern) else { return [] }
        let ns = text as NSString
        return rx.matches(in: text, range: NSRange(location: 0, length: ns.length)).map { ns.substring(with: $0.range(at: 1)) }
    }
}

/// Recibe la conexión larga con los avisos de la TV a medida que llegan.
private final class StreamDelegate: NSObject, URLSessionDataDelegate {
    weak var owner: TVCast?
    init(_ owner: TVCast) { self.owner = owner }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        owner?.streamResponse((response as? HTTPURLResponse)?.statusCode ?? 0)
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        owner?.streamData(data)
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        owner?.streamEnded(task, error: error)
    }
}

/**
 Mantiene edutube despierto en segundo plano mientras escucha los anuncios de la TV:
 iOS suspende las apps que no están sonando, así que se reproduce silencio (sin cortar otra música).
 */
private final class KeepAlive {
    private var player: AVAudioPlayer?

    func start() {
        guard player == nil else { return }
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.mixWithOthers])
        try? AVAudioSession.sharedInstance().setActive(true)
        player = try? AVAudioPlayer(data: Self.silence)
        player?.numberOfLoops = -1
        player?.volume = 0
        player?.play()
    }

    func stop() {
        player?.stop()
        player = nil
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
    }

    /// Un segundo de silencio en WAV (8 kHz, 8 bits, mono).
    private static let silence: Data = {
        let samples = 8000
        var d = Data()
        func u32(_ v: UInt32) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        func u16(_ v: UInt16) { withUnsafeBytes(of: v.littleEndian) { d.append(contentsOf: $0) } }
        d.append(contentsOf: Array("RIFF".utf8)); u32(UInt32(36 + samples))
        d.append(contentsOf: Array("WAVEfmt ".utf8)); u32(16); u16(1); u16(1); u32(8000); u32(8000); u16(1); u16(8)
        d.append(contentsOf: Array("data".utf8)); u32(UInt32(samples))
        d.append(Data(repeating: 128, count: samples))
        return d
    }()
}
