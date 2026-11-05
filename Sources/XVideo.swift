import Foundation

/**
 Videos de X (Twitter): la página los reproduce por trozos que el Chromecast no puede abrir directamente,
 así que se pide a X el archivo mp4 del post (el mismo que usa para insertar posts en otras páginas).
 */
enum XVideo {
    /// Id del post si la página es x.com/usuario/status/123…
    static func postId(_ url: URL?) -> String? {
        guard let url = url, let host = url.host?.lowercased(),
              host.hasSuffix("x.com") || host.hasSuffix("twitter.com") else { return nil }
        let parts = url.path.split(separator: "/")
        guard let i = parts.firstIndex(of: "status"), i + 1 < parts.count else { return nil }
        let id = String(parts[i + 1])
        return id.allSatisfy(\.isNumber) && !id.isEmpty ? id : nil
    }

    /// Busca el mp4 de mejor calidad del post. Prueba dos fuentes y devuelve nil si ninguna responde.
    static func resolve(_ id: String, completion: @escaping (String?) -> Void) {
        let syndication = "https://cdn.syndication.twimg.com/tweet-result?id=\(id)&lang=es&token=\(token(id))"
        fetch(syndication) { json in
            if let url = json.flatMap(bestFromSyndication) { return completion(url) }
            fetch("https://api.vxtwitter.com/Twitter/status/\(id)") { json in
                completion(json.flatMap(bestFromVx))
            }
        }
    }

    private static func fetch(_ address: String, completion: @escaping ([String: Any]?) -> Void) {
        guard let url = URL(string: address) else { return completion(nil) }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", forHTTPHeaderField: "User-Agent")
        URLSession.shared.dataTask(with: req) { data, _, _ in
            let json = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async { completion(json) }
        }.resume()
    }

    private static func bestFromSyndication(_ json: [String: Any]) -> String? {
        var media = json["mediaDetails"] as? [[String: Any]] ?? []
        // Si el post cita a otro, el video puede venir en el post citado.
        if let quoted = json["quoted_tweet"] as? [String: Any] {
            media += quoted["mediaDetails"] as? [[String: Any]] ?? []
        }
        var best: (url: String, bitrate: Int)?
        for item in media {
            let variants = (item["video_info"] as? [String: Any])?["variants"] as? [[String: Any]] ?? []
            for v in variants where (v["content_type"] as? String) == "video/mp4" {
                guard let url = v["url"] as? String else { continue }
                let bitrate = (v["bitrate"] as? Int) ?? 0
                if best == nil || bitrate > best!.bitrate { best = (url, bitrate) }
            }
        }
        return best?.url
    }

    private static func bestFromVx(_ json: [String: Any]) -> String? {
        let media = json["media_extended"] as? [[String: Any]] ?? []
        return media.first { ($0["type"] as? String) == "video" || ($0["type"] as? String) == "gif" }?["url"] as? String
    }

    /// El mismo cálculo que usa X en sus inserciones: (id / 1e15 × π) escrito en base 36, sin ceros ni punto.
    static func token(_ id: String) -> String {
        let value = (Double(id) ?? 0) / 1e15 * Double.pi
        let digits = Array("0123456789abcdefghijklmnopqrstuvwxyz")
        var integer = value.rounded(.down)
        var fraction = value - integer
        var intPart = ""
        repeat {
            let d = Int(integer.truncatingRemainder(dividingBy: 36))
            intPart = String(digits[d]) + intPart
            integer = (integer / 36).rounded(.down)
        } while integer > 0
        var fracPart = ""
        for _ in 0..<11 where fraction > 0 {
            fraction *= 36
            let d = Int(fraction.rounded(.down))
            fracPart.append(digits[min(d, 35)])
            fraction -= Double(d)
        }
        return (intPart + fracPart).replacingOccurrences(of: "0", with: "")
    }
}
