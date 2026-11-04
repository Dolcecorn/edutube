import Foundation
import Network

/**
 Encuentra los Chromecast de la red Wi-Fi y abre YouTube en ellos, sin la librería de Google.
 Habla el protocolo de Cast directamente: conexión TLS al puerto del Chromecast, mensajes en
 protobuf con JSON adentro. Una vez abierto YouTube en el Chromecast, se le pide su "screenId"
 y el video se envía con TVCast, igual que a una TV vinculada por código.
 */
final class Chromecast {
    static let shared = Chromecast()

    struct Device: Hashable {
        let id: String
        let name: String
        let endpoint: NWEndpoint
    }

    private(set) var devices: [Device] = []
    var onChange: (() -> Void)?
    private var browser: NWBrowser?
    private var sessions: [CastSession] = []

    enum CastError: LocalizedError {
        case timeout, launch(String), connection(String), message(String)
        var errorDescription: String? {
            switch self {
            case .timeout: return "El Chromecast no respondió. Revisa que el iPhone esté en el mismo Wi-Fi."
            case .launch(let s): return "El Chromecast no pudo abrir YouTube (\(s))."
            case .connection(let s): return "No se pudo conectar con el Chromecast (\(s))."
            case .message(let s): return s
            }
        }
    }

    /// Busca Chromecast en la red local. La primera vez iOS pide permiso de "red local".
    func startDiscovery() {
        guard browser == nil else { return }
        let b = NWBrowser(for: .bonjourWithTXTRecord(type: "_googlecast._tcp", domain: nil), using: NWParameters())
        b.browseResultsChangedHandler = { [weak self] results, _ in
            let found: [Device] = results.compactMap { r in
                var name = "Chromecast"
                var id = "\(r.endpoint)"
                if case let .service(service, _, _, _) = r.endpoint { name = service; id = service }
                if case let .bonjour(txt) = r.metadata {
                    if let fn = txt["fn"], !fn.isEmpty { name = fn }
                    if let txtId = txt["id"], !txtId.isEmpty { id = txtId }
                }
                return Device(id: id, name: name, endpoint: r.endpoint)
            }
            DispatchQueue.main.async {
                self?.devices = found.sorted { $0.name < $1.name }
                self?.onChange?()
            }
        }
        b.stateUpdateHandler = { [weak self] state in
            if case .failed = state {
                DispatchQueue.main.async { self?.browser = nil }
            }
        }
        b.start(queue: .main)
        browser = b
    }

    /// Abre YouTube en el Chromecast y devuelve su screenId.
    func openYouTube(on device: Device, completion: @escaping (Result<String, Error>) -> Void) {
        run(CastSession(endpoint: device.endpoint, mode: .youtube), completion)
    }

    /**
     Envía un archivo de video (mp4, HLS…) al reproductor que trae el Chromecast. La TV recibe solo
     el video, a pantalla completa, sin la página ni sus anuncios.
     */
    func playMedia(_ media: Media, on device: Device, completion: @escaping (Result<String, Error>) -> Void) {
        run(CastSession(endpoint: device.endpoint, mode: .media(media)), completion)
    }

    struct Media {
        let url: String
        let title: String
        let time: Double

        var contentType: String {
            let u = url.lowercased()
            if u.contains(".m3u8") { return "application/x-mpegURL" }
            if u.contains(".mpd") { return "application/dash+xml" }
            if u.contains(".webm") { return "video/webm" }
            return "video/mp4"
        }
    }

    private func run(_ s: CastSession, _ completion: @escaping (Result<String, Error>) -> Void) {
        sessions.append(s)
        s.start { [weak self, weak s] result in
            self?.sessions.removeAll { $0 === s }
            completion(result)
        }
    }
}

/// Una conexión al Chromecast, solo el tiempo necesario para abrir la app (YouTube o el reproductor) y darle la orden.
private final class CastSession {
    enum Mode {
        case youtube
        case media(Chromecast.Media)
    }

    private static let youtubeApp = "233637DE"
    private static let mediaApp = "CC1AD845" // reproductor incluido en todo Chromecast
    private static let nsMedia = "urn:x-cast:com.google.cast.media"
    private static let nsConnection = "urn:x-cast:com.google.cast.tp.connection"
    private static let nsHeartbeat = "urn:x-cast:com.google.cast.tp.heartbeat"
    private static let nsReceiver = "urn:x-cast:com.google.cast.receiver"
    private static let nsYouTube = "urn:x-cast:com.google.youtube.mdx"

    private let conn: NWConnection
    private var buffer = Data()
    private var completion: ((Result<String, Error>) -> Void)?
    private var transportId: String?
    private var requestId = 1
    private let mode: Mode
    private var appId: String {
        if case .youtube = mode { return Self.youtubeApp }
        return Self.mediaApp
    }

    init(endpoint: NWEndpoint, mode: Mode) {
        self.mode = mode
        let tls = NWProtocolTLS.Options()
        // El Chromecast usa un certificado propio, no uno de una autoridad pública.
        sec_protocol_options_set_verify_block(tls.securityProtocolOptions, { _, _, complete in complete(true) }, .main)
        conn = NWConnection(to: endpoint, using: NWParameters(tls: tls))
    }

    func start(_ completion: @escaping (Result<String, Error>) -> Void) {
        self.completion = completion
        conn.stateUpdateHandler = { [weak self] state in
            guard let self = self else { return }
            switch state {
            case .ready:
                self.send(Self.nsConnection, to: "receiver-0", ["type": "CONNECT"])
                self.send(Self.nsReceiver, to: "receiver-0",
                          ["type": "LAUNCH", "appId": self.appId, "requestId": self.nextRequest()])
                self.receive()
            case .failed(let error):
                self.finish(.failure(Chromecast.CastError.connection(error.localizedDescription)))
            default:
                break
            }
        }
        conn.start(queue: .main)
        DispatchQueue.main.asyncAfter(deadline: .now() + 20) { [weak self] in
            self?.finish(.failure(Chromecast.CastError.timeout))
        }
    }

    private func nextRequest() -> Int {
        requestId += 1
        return requestId
    }

    private func finish(_ result: Result<String, Error>) {
        guard let c = completion else { return }
        completion = nil
        c(result)
        // Se cierra con calma: YouTube sigue abierto en el Chromecast.
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.conn.cancel() }
    }

    // MARK: - Mensajes

    private func handle(namespace: String, source: String, payload: String) {
        guard let json = (try? JSONSerialization.jsonObject(with: Data(payload.utf8))) as? [String: Any],
              let type = json["type"] as? String else { return }
        switch (namespace, type) {
        case (Self.nsHeartbeat, "PING"):
            send(Self.nsHeartbeat, to: source, ["type": "PONG"])
        case (Self.nsReceiver, "RECEIVER_STATUS"):
            let status = json["status"] as? [String: Any]
            let apps = status?["applications"] as? [[String: Any]] ?? []
            guard transportId == nil,
                  let app = apps.first(where: { ($0["appId"] as? String) == appId }),
                  let transport = app["transportId"] as? String else { return }
            transportId = transport
            send(Self.nsConnection, to: transport, ["type": "CONNECT"])
            switch mode {
            case .youtube:
                askScreenId(transport, attempt: 0)
            case .media(let media):
                send(Self.nsMedia, to: transport, [
                    "type": "LOAD", "requestId": nextRequest(), "autoplay": true, "currentTime": media.time,
                    "media": [
                        "contentId": media.url, "contentUrl": media.url, "contentType": media.contentType,
                        "streamType": "BUFFERED",
                        "metadata": ["metadataType": 0, "title": media.title],
                    ] as [String: Any],
                ])
            }
        case (Self.nsReceiver, "LAUNCH_ERROR"):
            finish(.failure(Chromecast.CastError.launch(json["reason"] as? String ?? "error")))
        case (Self.nsMedia, "MEDIA_STATUS"):
            let status = (json["status"] as? [[String: Any]])?.first
            if let state = status?["playerState"] as? String, state != "IDLE" {
                finish(.success("ok"))
            } else if (status?["idleReason"] as? String) == "ERROR" {
                finish(.failure(Chromecast.CastError.message("La TV no pudo abrir este video")))
            }
        case (Self.nsMedia, "LOAD_FAILED"), (Self.nsMedia, "LOAD_CANCELLED"), (Self.nsMedia, "INVALID_REQUEST"):
            finish(.failure(Chromecast.CastError.message("La TV no pudo abrir este video")))
        case (Self.nsYouTube, "mdxSessionStatus"):
            let data = json["data"] as? [String: Any]
            if let screenId = data?["screenId"] as? String {
                finish(.success(screenId))
            }
        default:
            break
        }
    }

    /// YouTube tarda un poco en arrancar en el Chromecast; se pregunta hasta que contesta.
    private func askScreenId(_ transport: String, attempt: Int) {
        guard completion != nil, attempt < 10 else { return }
        send(Self.nsYouTube, to: transport, ["type": "getMdxSessionStatus"])
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.askScreenId(transport, attempt: attempt + 1)
        }
    }

    private func send(_ namespace: String, to destination: String, _ payload: [String: Any]) {
        guard let json = try? JSONSerialization.data(withJSONObject: payload),
              let text = String(data: json, encoding: .utf8) else { return }
        var msg = Data()
        msg.appendVarintField(1, 0) // protocol_version = CASTV2_1_0
        msg.appendStringField(2, "sender-0")
        msg.appendStringField(3, destination)
        msg.appendStringField(4, namespace)
        msg.appendVarintField(5, 0) // payload_type = STRING
        msg.appendStringField(6, text)
        var frame = Data()
        let len = UInt32(msg.count)
        frame.append(contentsOf: [UInt8(len >> 24 & 0xFF), UInt8(len >> 16 & 0xFF), UInt8(len >> 8 & 0xFF), UInt8(len & 0xFF)])
        frame.append(msg)
        conn.send(content: frame, completion: .contentProcessed { _ in })
    }

    private func receive() {
        conn.receive(minimumIncompleteLength: 1, maximumLength: 65_536) { [weak self] data, _, isComplete, error in
            guard let self = self else { return }
            if let data = data { self.buffer.append(data); self.parseFrames() }
            if let error = error {
                self.finish(.failure(Chromecast.CastError.connection(error.localizedDescription)))
            } else if !isComplete {
                self.receive()
            }
        }
    }

    private func parseFrames() {
        while buffer.count >= 4 {
            let b = [UInt8](buffer.prefix(4))
            let len = Int(b[0]) << 24 | Int(b[1]) << 16 | Int(b[2]) << 8 | Int(b[3])
            guard buffer.count >= 4 + len else { return }
            let body = [UInt8](buffer.dropFirst(4).prefix(len))
            buffer = Data(buffer.dropFirst(4 + len))
            var namespace = "", source = "", payload = ""
            var i = 0
            while i < body.count {
                guard let key = Self.varint(body, &i) else { break }
                let field = key >> 3, wire = key & 7
                if wire == 0 {
                    _ = Self.varint(body, &i)
                } else if wire == 2 {
                    guard let n = Self.varint(body, &i), i + n <= body.count else { break }
                    let text = String(decoding: body[i..<i + n], as: UTF8.self)
                    i += n
                    switch field {
                    case 2: source = text
                    case 4: namespace = text
                    case 6: payload = text
                    default: break
                    }
                } else {
                    break
                }
            }
            handle(namespace: namespace, source: source, payload: payload)
        }
    }

    private static func varint(_ bytes: [UInt8], _ i: inout Int) -> Int? {
        var result = 0, shift = 0
        while i < bytes.count {
            let b = bytes[i]
            i += 1
            result |= Int(b & 0x7F) << shift
            if b & 0x80 == 0 { return result }
            shift += 7
        }
        return nil
    }
}

private extension Data {
    mutating func appendVarint(_ value: Int) {
        var v = UInt64(value)
        repeat {
            var byte = UInt8(v & 0x7F)
            v >>= 7
            if v != 0 { byte |= 0x80 }
            append(byte)
        } while v != 0
    }

    mutating func appendVarintField(_ field: Int, _ value: Int) {
        appendVarint(field << 3 | 0)
        appendVarint(value)
    }

    mutating func appendStringField(_ field: Int, _ value: String) {
        let bytes = Data(value.utf8)
        appendVarint(field << 3 | 2)
        appendVarint(bytes.count)
        append(bytes)
    }
}
