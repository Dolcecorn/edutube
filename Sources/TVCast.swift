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
            self.loungeToken = token
            self.resetSession()
            self.done(completion, .success(name))
        }
    }

    func unpair() {
        prefs.removeObject(forKey: "cast.screen")
        prefs.removeObject(forKey: "cast.name")
        loungeToken = nil
        resetSession()
    }

    // MARK: - Enviar

    /// Reproduce el video en la TV desde el segundo indicado.
    func cast(videoId: String, at time: Double, completion: @escaping (Result<String, Error>) -> Void) {
        guard isPaired else { return done(completion, .failure(CastError.notPaired)) }
        var params = ["videoId": videoId, "currentTime": String(Int(time)), "currentIndex": "0",
                      "videoIds": videoId, "listId": "", "audioOnly": "false", "params": "", "playerParams": ""]
        if time < 1 { params["currentTime"] = "0" }
        command("setPlaylist", params: params, retry: true) { result in
            self.done(completion, result.map { _ in self.screenName ?? "TV" })
        }
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
        guard let id = screenId else { return completion(false) }
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
