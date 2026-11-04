import ReplayKit
import UIKit

/// Espejo de pantalla: abre el aviso de iOS para "Iniciar transmisión" y espera a que la extensión esté sirviendo video.
enum ScreenMirror {
    static let port = 8090

    /// La extensión viene dentro de la app; se busca por si el instalador le cambió el identificador.
    static var extensionId: String? {
        guard let dir = Bundle.main.builtInPlugInsURL,
              let items = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil) else { return nil }
        return items.first { $0.pathExtension == "appex" }.flatMap { Bundle(url: $0)?.bundleIdentifier }
    }

    private static var picker: RPSystemBroadcastPickerView?

    /// Muestra el aviso del sistema para iniciar (o detener) el espejo.
    static func showSystemPicker(in view: UIView) {
        picker?.removeFromSuperview()
        let p = RPSystemBroadcastPickerView(frame: CGRect(x: -100, y: -100, width: 44, height: 44))
        p.preferredExtension = extensionId
        p.showsMicrophoneButton = false
        p.alpha = 0.01
        view.addSubview(p)
        picker = p
        func press(_ v: UIView) {
            if let b = v as? UIButton { b.sendActions(for: .touchUpInside); return }
            v.subviews.forEach(press)
        }
        press(p)
    }

    /// Avisa cuando la extensión ya tiene unos segundos de video listos (o se rinde tras `timeout`).
    static func waitUntilLive(timeout: TimeInterval = 60, completion: @escaping (Bool) -> Void) {
        let deadline = Date().addingTimeInterval(timeout)
        func check() {
            var req = URLRequest(url: URL(string: "http://127.0.0.1:\(port)/live.m3u8")!, timeoutInterval: 2)
            req.cachePolicy = .reloadIgnoringLocalCacheData
            URLSession.shared.dataTask(with: req) { _, resp, _ in
                DispatchQueue.main.async {
                    if (resp as? HTTPURLResponse)?.statusCode == 200 { return completion(true) }
                    if Date() > deadline { return completion(false) }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 1, execute: check)
                }
            }.resume()
        }
        check()
    }

    /// Dirección del iPhone en el Wi-Fi, para que el Chromecast pueda pedirle el video.
    static func wifiAddress() -> String? {
        var ifaddr: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&ifaddr) == 0, let first = ifaddr else { return nil }
        defer { freeifaddrs(ifaddr) }
        var fallback: String?
        for ptr in sequence(first: first, next: { $0.pointee.ifa_next }) {
            let ifa = ptr.pointee
            guard let addr = ifa.ifa_addr, addr.pointee.sa_family == UInt8(AF_INET) else { continue }
            let name = String(cString: ifa.ifa_name)
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            getnameinfo(addr, socklen_t(addr.pointee.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST)
            let ip = String(cString: host)
            if name == "en0" { return ip }
            if name.hasPrefix("en"), !ip.hasPrefix("169.254") { fallback = ip }
        }
        return fallback
    }
}
