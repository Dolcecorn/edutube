import Foundation
import Network

/**
 Servidor web mínimo en el puerto 8090: entrega la lista "live.m3u8" y los trozos de video
 para que el Chromecast los vaya pidiendo. Guarda solo los últimos segundos.
 */
final class HLSServer {
    static let port: UInt16 = 8090
    private static let keep = 6

    private var listener: NWListener?
    private let queue = DispatchQueue(label: "hls-server")
    private var initSegment: Data?
    private var segments: [(seq: Int, data: Data, duration: Double)] = []
    private var nextSeq = 0

    func start() {
        guard let l = try? NWListener(using: .tcp, on: NWEndpoint.Port(rawValue: Self.port)!) else { return }
        l.newConnectionHandler = { [weak self] conn in self?.serve(conn) }
        l.start(queue: queue)
        listener = l
    }

    func stop() {
        listener?.cancel()
        listener = nil
    }

    func setInit(_ data: Data) {
        queue.async { self.initSegment = data }
    }

    func addSegment(_ data: Data, duration: Double) {
        queue.async {
            self.segments.append((self.nextSeq, data, duration))
            self.nextSeq += 1
            if self.segments.count > Self.keep { self.segments.removeFirst(self.segments.count - Self.keep) }
        }
    }

    private func playlist() -> String? {
        // Se espera a tener 3 trozos para que la TV no se quede sin video apenas empieza.
        guard initSegment != nil, segments.count >= 3, let first = segments.first else { return nil }
        let target = Int((segments.map(\.duration).max() ?? 1).rounded(.up))
        var lines = [
            "#EXTM3U", "#EXT-X-VERSION:7", "#EXT-X-TARGETDURATION:\(max(target, 1))",
            "#EXT-X-MEDIA-SEQUENCE:\(first.seq)", "#EXT-X-INDEPENDENT-SEGMENTS", "#EXT-X-MAP:URI=\"init.mp4\"",
        ]
        for s in segments {
            lines.append(String(format: "#EXTINF:%.3f,", s.duration))
            lines.append("seg\(s.seq).m4s")
        }
        return lines.joined(separator: "\n") + "\n"
    }

    private func serve(_ conn: NWConnection) {
        conn.start(queue: queue)
        conn.receive(minimumIncompleteLength: 1, maximumLength: 8192) { [weak self] data, _, _, _ in
            guard let self = self else { return conn.cancel() }
            let request = data.flatMap { String(data: $0, encoding: .utf8) } ?? ""
            let parts = request.split(separator: " ")
            let method = parts.first.map(String.init) ?? "GET"
            var path = parts.count > 1 ? String(parts[1]) : "/"
            if let q = path.firstIndex(of: "?") { path = String(path[..<q]) }

            var status = "200 OK", type = "application/octet-stream", body = Data()
            if method == "OPTIONS" {
                body = Data()
            } else if path == "/live.m3u8" {
                if let p = self.playlist() {
                    type = "application/vnd.apple.mpegurl"
                    body = Data(p.utf8)
                } else {
                    status = "404 Not Found"
                }
            } else if path == "/init.mp4", let i = self.initSegment {
                type = "video/mp4"
                body = i
            } else if path.hasPrefix("/seg"), path.hasSuffix(".m4s"),
                      let n = Int(path.dropFirst(4).dropLast(4)),
                      let seg = self.segments.first(where: { $0.seq == n }) {
                type = "video/iso.segment"
                body = seg.data
            } else {
                status = "404 Not Found"
            }
            // El reproductor del Chromecast pide los archivos desde una página web: necesita permiso CORS.
            let head = "HTTP/1.1 \(status)\r\nContent-Type: \(type)\r\nContent-Length: \(method == "HEAD" ? 0 : body.count)\r\n"
                + "Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Headers: *\r\nAccess-Control-Allow-Methods: GET, HEAD, OPTIONS\r\n"
                + "Cache-Control: no-cache\r\nConnection: close\r\n\r\n"
            var response = Data(head.utf8)
            if method != "HEAD" { response.append(body) }
            conn.send(content: response, completion: .contentProcessed { _ in conn.cancel() })
        }
    }
}
