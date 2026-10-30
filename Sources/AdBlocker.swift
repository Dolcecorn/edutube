import Foundation
import WebKit

/**
 Bloquea peticiones a dominios de anuncios usando las listas incluidas en la app.
 En iOS no se pueden interceptar las peticiones de WKWebView una por una, así que las listas
 se convierten en reglas de contenido de WebKit (WKContentRuleList), que se compilan la primera
 vez que se abre la app y quedan guardadas para las siguientes.
 */
final class AdBlocker {
    static let shared = AdBlocker()

    /// Sube este número si cambias las listas, para que se vuelvan a compilar.
    private static let version = 1
    /// WebKit compila más rápido varias listas medianas que una gigante.
    private static let chunkSize = 20_000

    private var hosts = Set<String>()
    private(set) var ruleLists: [WKContentRuleList] = []
    private var listeners: [(WKContentRuleList) -> Void] = []
    private var started = false

    var blockedCount: Int { hosts.count }

    /// Recibe cada lista apenas está lista (también las que ya estaban listas antes de llamar).
    func onRuleList(_ handler: @escaping (WKContentRuleList) -> Void) {
        ruleLists.forEach(handler)
        listeners.append(handler)
    }

    func prepare() {
        guard !started else { return }
        started = true
        DispatchQueue.global(qos: .userInitiated).async {
            // La lista corta (redes de anuncios de video) va sola para que funcione desde el primer video.
            let extra = Self.read("extra_hosts")
            let all = Self.dedupe(extra.union(Self.read("adhosts")))
            let extraChunk = all.filter { extra.contains($0) }.sorted()
            let rest = all.filter { !extra.contains($0) }.sorted()
            var chunks = [extraChunk]
            var i = 0
            while i < rest.count {
                chunks.append(Array(rest[i..<min(i + Self.chunkSize, rest.count)]))
                i += Self.chunkSize
            }
            DispatchQueue.main.async {
                self.hosts = all
                for (n, chunk) in chunks.enumerated() where !chunk.isEmpty {
                    self.loadOrCompile(id: "ads-v\(Self.version)-\(all.count)-\(n)", hosts: chunk)
                }
            }
        }
    }

    /// true si el host o cualquiera de sus dominios padre está en la lista.
    func isBlocked(_ host: String?) -> Bool {
        guard var h = host?.lowercased() else { return false }
        while true {
            if hosts.contains(h) { return true }
            guard let dot = h.firstIndex(of: "."), h[h.index(after: dot)...].contains(".") else { return false }
            h = String(h[h.index(after: dot)...])
        }
    }

    // MARK: - Privado

    private func loadOrCompile(id: String, hosts: [String]) {
        guard let store = WKContentRuleListStore.default() else { return }
        store.lookUpContentRuleList(forIdentifier: id) { list, _ in
            if let list = list {
                self.publish(list)
                return
            }
            DispatchQueue.global(qos: .userInitiated).async {
                let json = Self.rulesJSON(hosts)
                DispatchQueue.main.async {
                    store.compileContentRuleList(forIdentifier: id, encodedContentRuleList: json) { list, error in
                        if let list = list {
                            self.publish(list)
                        } else if let error = error {
                            NSLog("TVWeb: no se pudo compilar %@: %@", id, error.localizedDescription)
                        }
                    }
                }
            }
        }
        // Borra listas de versiones anteriores.
        store.getAvailableContentRuleListIdentifiers { ids in
            for old in ids ?? [] where old.hasPrefix("ads-") && !old.hasPrefix("ads-v\(Self.version)-\(self.hosts.count)-") {
                store.removeContentRuleList(forIdentifier: old) { _ in }
            }
        }
    }

    private func publish(_ list: WKContentRuleList) {
        ruleLists.append(list)
        listeners.forEach { $0(list) }
    }

    private static func read(_ name: String) -> Set<String> {
        guard let url = Bundle.main.url(forResource: name, withExtension: "txt"),
              let text = try? String(contentsOf: url, encoding: .utf8) else { return [] }
        var out = Set<String>()
        for raw in text.split(whereSeparator: \.isNewline) {
            let line = raw.trimmingCharacters(in: .whitespaces).lowercased()
            if line.isEmpty || line.hasPrefix("#") { continue }
            out.insert(line)
        }
        return out
    }

    /// Quita subdominios cuyo dominio padre ya está bloqueado (las reglas ya los cubren).
    private static func dedupe(_ set: Set<String>) -> Set<String> {
        set.filter { host in
            var h = Substring(host)
            while let dot = h.firstIndex(of: ".") {
                h = h[h.index(after: dot)...]
                if !h.contains(".") { break }
                if set.contains(String(h)) { return false }
            }
            return true
        }
    }

    private static func rulesJSON(_ hosts: [String]) -> String {
        // WebKit no acepta "|" en las expresiones; una regla por dominio, que cubre también sus subdominios.
        let rules: [[String: Any]] = hosts.map { host in
            let escaped = host.replacingOccurrences(of: ".", with: "\\.")
            return [
                "trigger": ["url-filter": "^[htpsw]+://([a-z0-9.-]+\\.)?\(escaped)[:/]"],
                "action": ["type": "block"],
            ]
        }
        let data = (try? JSONSerialization.data(withJSONObject: rules)) ?? Data("[]".utf8)
        return String(decoding: data, as: UTF8.self)
    }
}
