import UIKit

/**
 "TV gratis": catálogo de fuentes legales, oficiales y gratuitas (canales chilenos, canales gratis 24/7,
 deportes, películas, series y cortos). No hay listas piratas: cada entrada abre el canal o la página
 oficial dentro de edutube, y desde ahí el botón rojo lo manda al Chromecast.
 */
enum FreeTV {
    enum Kind {
        /// Página o búsqueda de YouTube: se transmite con el Chromecast igual que cualquier video de YouTube.
        case youtube
        /// Página oficial del servicio: el botón rojo envía el video que se está viendo (o el espejo de pantalla).
        case web
    }

    struct Item {
        let title: String
        let detail: String
        let url: String
        let kind: Kind
        let symbol: String
        var live = false
    }

    struct Section {
        let title: String
        let note: String?
        let items: [Item]
    }

    /// Búsqueda en YouTube solo de transmisiones en vivo ahora.
    private static func liveSearch(_ q: String) -> String {
        "https://m.youtube.com/results?search_query=\(q.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? q)&sp=EgJAAQ%253D%253D"
    }

    private static func search(_ q: String) -> String {
        "https://m.youtube.com/results?search_query=\(q.addingPercentEncoding(withAllowedCharacters: .alphanumerics) ?? q)"
    }

    private static func channel(_ handle: String, _ tab: String = "") -> String {
        "https://m.youtube.com/@\(handle)\(tab.isEmpty ? "" : "/" + tab)"
    }

    static let sections: [Section] = [
        Section(title: "TV chilena en vivo", note: "Señales oficiales que los propios canales transmiten gratis por YouTube y en sus páginas.", items: [
            Item(title: "24 Horas (TVN)", detail: "Noticias en vivo, señal oficial de TVN", url: liveSearch("24 Horas en vivo TVN"), kind: .youtube, symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "T13 En Vivo (Canal 13)", detail: "Noticias en vivo, señal oficial de Canal 13", url: liveSearch("T13 en vivo"), kind: .youtube, symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "CHV Noticias (Chilevisión)", detail: "Noticias en vivo, señal oficial de Chilevisión", url: liveSearch("CHV Noticias en vivo"), kind: .youtube, symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "Meganoticias (Mega)", detail: "Noticias en vivo, señal oficial de Mega", url: liveSearch("Meganoticias en vivo"), kind: .youtube, symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "Canal 13: señal en vivo", detail: "Página oficial de Canal 13", url: "https://www.13.cl/en-vivo", kind: .web, symbol: "tv", live: true),
            Item(title: "TVN: señal en vivo", detail: "Página oficial de TVN (toca «En vivo»)", url: "https://www.tvn.cl", kind: .web, symbol: "tv", live: true),
            Item(title: "Mega: señal en vivo", detail: "Página oficial de Mega (toca «En vivo»)", url: "https://www.mega.cl", kind: .web, symbol: "tv", live: true),
            Item(title: "Chilevisión: señal en vivo", detail: "Página oficial de CHV (toca «Señal online»)", url: "https://www.chilevision.cl", kind: .web, symbol: "tv", live: true),
        ]),
        Section(title: "Canales gratis 24/7", note: "Servicios legales que se financian con publicidad: aquí sus anuncios no se bloquean, para que funcionen bien.", items: [
            Item(title: "Pluto TV en vivo", detail: "Cientos de canales: películas, series, deportes, noticias", url: "https://pluto.tv/latam/live-tv", kind: .web, symbol: "play.tv", live: true),
            Item(title: "Plex: TV gratis", detail: "Canales en vivo gratis", url: "https://watch.plex.tv/live-tv", kind: .web, symbol: "play.tv", live: true),
            Item(title: "Red Bull TV", detail: "Deportes extremos y eventos en vivo", url: "https://www.redbull.com/cl-es/discover", kind: .web, symbol: "bolt.fill", live: true),
            Item(title: "Red Bull en YouTube (en vivo)", detail: "Transmisiones oficiales de Red Bull", url: channel("redbull", "streams"), kind: .youtube, symbol: "bolt.fill", live: true),
        ]),
        Section(title: "Automovilismo", note: "Las carreras completas en vivo de F1, IndyCar y NASCAR son de pago (F1 TV, ESPN, Star+). GT World Challenge e IMSA transmiten carreras completas gratis en YouTube; el resto, resúmenes y repeticiones oficiales.", items: [
            Item(title: "GT World Challenge", detail: "Carreras completas en vivo y gratis", url: channel("GTWorld", "streams"), kind: .youtube, symbol: "flag.checkered", live: true),
            Item(title: "IMSA", detail: "Carreras en vivo gratis fuera de EE. UU.", url: channel("IMSA", "streams"), kind: .youtube, symbol: "flag.checkered", live: true),
            Item(title: "WEC (Mundial de Resistencia)", detail: "Resúmenes y transmisiones oficiales", url: channel("FIAWEC", "streams"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "Fórmula E", detail: "Carreras completas y resúmenes oficiales", url: channel("FIAFormulaE", "videos"), kind: .youtube, symbol: "bolt.car"),
            Item(title: "Fórmula 1", detail: "Resúmenes oficiales de cada carrera", url: channel("Formula1", "videos"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "IndyCar", detail: "Resúmenes oficiales", url: channel("INDYCAR", "videos"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "NASCAR", detail: "Resúmenes oficiales", url: channel("NASCAR", "videos"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "MotoGP", detail: "Resúmenes oficiales", url: channel("MotoGP", "videos"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "WRC (Rally)", detail: "Resúmenes oficiales", url: channel("WRC", "videos"), kind: .youtube, symbol: "flag.checkered"),
            Item(title: "Carreras en vivo ahora", detail: "Búsqueda de transmisiones en vivo de automovilismo", url: liveSearch("GT World Challenge IMSA en vivo"), kind: .youtube, symbol: "dot.radiowaves.left.and.right", live: true),
        ]),
        Section(title: "Fútbol", note: "Los partidos completos del Campeonato chileno, Libertadores, MLS y ligas europeas son de pago (TNT Sports, ESPN, Apple TV, Disney+). Aquí están los resúmenes oficiales y los partidos que FIFA+ da gratis.", items: [
            Item(title: "FIFA+", detail: "Partidos en vivo gratis de algunas ligas y archivo de Mundiales", url: "https://www.plus.fifa.com/es/", kind: .web, symbol: "soccerball", live: true),
            Item(title: "Campeonato chileno", detail: "Resúmenes y goles de la fecha", url: search("resumen campeonato chileno TNT Sports"), kind: .youtube, symbol: "soccerball"),
            Item(title: "CONMEBOL (Libertadores, Sudamericana)", detail: "Resúmenes oficiales", url: search("CONMEBOL resumen"), kind: .youtube, symbol: "soccerball"),
            Item(title: "MLS", detail: "Resúmenes oficiales", url: channel("MLS", "videos"), kind: .youtube, symbol: "soccerball"),
            Item(title: "LaLiga", detail: "Resúmenes oficiales", url: channel("LaLiga", "videos"), kind: .youtube, symbol: "soccerball"),
            Item(title: "Premier League", detail: "Resúmenes oficiales", url: channel("premierleague", "videos"), kind: .youtube, symbol: "soccerball"),
            Item(title: "Serie A", detail: "Resúmenes oficiales", url: channel("SerieA", "videos"), kind: .youtube, symbol: "soccerball"),
            Item(title: "Bundesliga", detail: "Resúmenes oficiales", url: channel("bundesliga", "videos"), kind: .youtube, symbol: "soccerball"),
            Item(title: "Champions League", detail: "Resúmenes oficiales de la UEFA", url: search("UEFA Champions League resumen"), kind: .youtube, symbol: "soccerball"),
        ]),
        Section(title: "Películas y series", note: "Catálogos gratis y legales. Los que piden cuenta (Plex, ViX) son gratis igual.", items: [
            Item(title: "Pluto TV a pedido", detail: "Películas y series completas gratis", url: "https://pluto.tv/latam/on-demand", kind: .web, symbol: "film"),
            Item(title: "Ondamedia", detail: "Cine chileno gratis (Ministerio de las Culturas)", url: "https://ondamedia.cl", kind: .web, symbol: "film"),
            Item(title: "CNTV Play", detail: "Series y documentales chilenos gratis", url: "https://cntvplay.cl", kind: .web, symbol: "film"),
            Item(title: "Plex: películas gratis", detail: "Miles de películas y series con anuncios", url: "https://watch.plex.tv", kind: .web, symbol: "film"),
            Item(title: "ViX (plan gratis)", detail: "Películas, series y novelas en español", url: "https://vix.com", kind: .web, symbol: "film"),
            Item(title: "Tubi", detail: "Películas y series gratis (si está disponible en Chile)", url: "https://tubitv.com", kind: .web, symbol: "film"),
            Item(title: "Clásicos de dominio público", detail: "Películas antiguas libres de derechos (Internet Archive)", url: "https://archive.org/details/feature_films", kind: .web, symbol: "film.stack"),
        ]),
        Section(title: "Cortometrajes", note: nil, items: [
            Item(title: "Omeleto", detail: "Cortometrajes premiados", url: channel("Omeleto", "videos"), kind: .youtube, symbol: "film.circle"),
            Item(title: "DUST", detail: "Cortos de ciencia ficción", url: channel("watchdust", "videos"), kind: .youtube, symbol: "film.circle"),
            Item(title: "ALTER", detail: "Cortos de terror", url: channel("alter", "videos"), kind: .youtube, symbol: "film.circle"),
            Item(title: "Cortos chilenos en Ondamedia", detail: "Cortometrajes nacionales gratis", url: "https://ondamedia.cl", kind: .web, symbol: "film.circle"),
            Item(title: "Cortometrajes en español", detail: "Búsqueda en YouTube", url: search("cortometraje en español completo"), kind: .youtube, symbol: "magnifyingglass"),
        ]),
    ]

    /// Servicios gratis que viven de su publicidad: ahí no se bloquean anuncios (si no, sus reproductores fallan).
    private static let adSupported = [
        "pluto.tv", "plex.tv", "tubitv.com", "vix.com", "fifa.com", "redbull.com", "ondamedia.cl", "cntvplay.cl",
        "archive.org", "13.cl", "tvn.cl", "24horas.cl", "mega.cl", "meganoticias.cl", "chilevision.cl",
    ]

    static func isAdSupported(_ host: String?) -> Bool {
        guard let h = host?.lowercased() else { return false }
        return adSupported.contains { h == $0 || h.hasSuffix("." + $0) }
    }
}

/// Pantalla con el catálogo. Al elegir algo se cierra y edutube abre esa página.
final class FreeTVViewController: UITableViewController {
    var onOpen: ((FreeTV.Item) -> Void)?
    var onMirror: (() -> Void)?

    private let sections = FreeTV.sections
    private let red = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 1)

    init() { super.init(style: .insetGrouped) }
    required init?(coder: NSCoder) { fatalError() }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "TV gratis"
        navigationItem.leftBarButtonItem = UIBarButtonItem(title: "YouTube", style: .plain, target: self, action: #selector(close))
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            image: UIImage(systemName: "rectangle.on.rectangle"), style: .plain, target: self, action: #selector(mirror))
        navigationItem.rightBarButtonItem?.accessibilityLabel = "Espejo de pantalla en la TV"
        tableView.register(UITableViewCell.self, forCellReuseIdentifier: "c")
        tableView.tableHeaderView = header()
        Chromecast.shared.startDiscovery()
    }

    private func header() -> UIView {
        let label = UILabel()
        label.numberOfLines = 0
        label.font = .preferredFont(forTextStyle: .footnote)
        label.textColor = .secondaryLabel
        label.text = "Solo fuentes oficiales, legales y gratuitas. Todo se puede mandar al Chromecast con el botón rojo "
            + "(si una página no deja enviar su video, usa el espejo de pantalla, arriba a la derecha).\n\n"
            + "Ojo: la mayoría de los partidos y carreras completos en vivo son de pago; aquí está lo que las ligas y "
            + "canales dan gratis."
        let w = view.bounds.width - 40
        let size = label.sizeThatFits(CGSize(width: w, height: .greatestFiniteMagnitude))
        label.frame = CGRect(x: 20, y: 12, width: w, height: size.height)
        let box = UIView(frame: CGRect(x: 0, y: 0, width: view.bounds.width, height: size.height + 20))
        label.autoresizingMask = [.flexibleWidth]
        box.addSubview(label)
        return box
    }

    @objc private func close() { dismiss(animated: true) }

    @objc private func mirror() {
        dismiss(animated: true) { [onMirror] in onMirror?() }
    }

    override func numberOfSections(in tableView: UITableView) -> Int { sections.count }

    override func tableView(_ tableView: UITableView, numberOfRowsInSection section: Int) -> Int {
        sections[section].items.count
    }

    override func tableView(_ tableView: UITableView, titleForHeaderInSection section: Int) -> String? {
        sections[section].title
    }

    override func tableView(_ tableView: UITableView, titleForFooterInSection section: Int) -> String? {
        sections[section].note
    }

    override func tableView(_ tableView: UITableView, cellForRowAt indexPath: IndexPath) -> UITableViewCell {
        let item = sections[indexPath.section].items[indexPath.row]
        let cell = tableView.dequeueReusableCell(withIdentifier: "c", for: indexPath)
        var content = UIListContentConfiguration.subtitleCell()
        content.text = item.title
        content.secondaryText = item.detail
        content.secondaryTextProperties.color = .secondaryLabel
        content.image = UIImage(systemName: item.symbol) ?? UIImage(systemName: "play.rectangle")
        content.imageProperties.tintColor = item.kind == .youtube ? red : .systemBlue
        cell.contentConfiguration = content
        if item.live {
            let badge = UILabel()
            badge.text = " EN VIVO "
            badge.font = .systemFont(ofSize: 10, weight: .bold)
            badge.textColor = .white
            badge.backgroundColor = red
            badge.layer.cornerRadius = 4
            badge.clipsToBounds = true
            badge.sizeToFit()
            cell.accessoryView = badge
        } else {
            cell.accessoryView = nil
            cell.accessoryType = .disclosureIndicator
        }
        return cell
    }

    override func tableView(_ tableView: UITableView, didSelectRowAt indexPath: IndexPath) {
        tableView.deselectRow(at: indexPath, animated: true)
        let item = sections[indexPath.section].items[indexPath.row]
        dismiss(animated: true) { [onOpen] in onOpen?(item) }
    }
}
