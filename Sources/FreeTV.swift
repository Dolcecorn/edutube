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
        /// Dominio oficial del que se toma el logo.
        let logo: String
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
            Item(title: "24 Horas (TVN)", detail: "Noticias en vivo, señal oficial de TVN", url: liveSearch("24 Horas en vivo TVN"), kind: .youtube, logo: "24horas.cl", symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "T13 En Vivo (Canal 13)", detail: "Noticias en vivo, señal oficial de Canal 13", url: liveSearch("T13 en vivo"), kind: .youtube, logo: "t13.cl", symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "CHV Noticias (Chilevisión)", detail: "Noticias en vivo, señal oficial de Chilevisión", url: liveSearch("CHV Noticias en vivo"), kind: .youtube, logo: "chvnoticias.cl", symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "Meganoticias (Mega)", detail: "Noticias en vivo, señal oficial de Mega", url: liveSearch("Meganoticias en vivo"), kind: .youtube, logo: "meganoticias.cl", symbol: "antenna.radiowaves.left.and.right", live: true),
            Item(title: "Canal 13: señal en vivo", detail: "Página oficial de Canal 13", url: "https://www.13.cl/en-vivo", kind: .web, logo: "13.cl", symbol: "tv", live: true),
            Item(title: "TVN: señal en vivo", detail: "Página oficial de TVN (toca «En vivo»)", url: "https://www.tvn.cl", kind: .web, logo: "tvn.cl", symbol: "tv", live: true),
            Item(title: "Mega: señal en vivo", detail: "Página oficial de Mega (toca «En vivo»)", url: "https://www.mega.cl", kind: .web, logo: "mega.cl", symbol: "tv", live: true),
            Item(title: "Chilevisión: señal en vivo", detail: "Página oficial de CHV (toca «Señal online»)", url: "https://www.chilevision.cl", kind: .web, logo: "chilevision.cl", symbol: "tv", live: true),
        ]),
        Section(title: "Canales gratis 24/7", note: "Servicios legales que se financian con publicidad: aquí sus anuncios no se bloquean, para que funcionen bien.", items: [
            Item(title: "Pluto TV en vivo", detail: "Cientos de canales: películas, series, deportes, noticias", url: "https://pluto.tv/latam/live-tv", kind: .web, logo: "pluto.tv", symbol: "play.tv", live: true),
            Item(title: "Plex: TV gratis", detail: "Canales en vivo gratis", url: "https://watch.plex.tv/live-tv", kind: .web, logo: "plex.tv", symbol: "play.tv", live: true),
            Item(title: "Red Bull TV", detail: "Deportes extremos y eventos en vivo", url: "https://www.redbull.com/cl-es/discover", kind: .web, logo: "redbull.com", symbol: "bolt.fill", live: true),
            Item(title: "Red Bull en YouTube (en vivo)", detail: "Transmisiones oficiales de Red Bull", url: channel("redbull", "streams"), kind: .youtube, logo: "redbull.com", symbol: "bolt.fill", live: true),
        ]),
        Section(title: "Automovilismo", note: "Las carreras completas en vivo de F1, IndyCar y NASCAR son de pago (F1 TV, ESPN, Star+). GT World Challenge e IMSA transmiten carreras completas gratis en YouTube; el resto, resúmenes y repeticiones oficiales.", items: [
            Item(title: "GT World Challenge", detail: "Carreras completas en vivo y gratis", url: channel("GTWorld", "streams"), kind: .youtube, logo: "gt-world-challenge-europe.com", symbol: "flag.checkered", live: true),
            Item(title: "IMSA", detail: "Carreras en vivo gratis fuera de EE. UU.", url: channel("IMSA", "streams"), kind: .youtube, logo: "imsa.com", symbol: "flag.checkered", live: true),
            Item(title: "WEC (Mundial de Resistencia)", detail: "Resúmenes y transmisiones oficiales", url: channel("FIAWEC", "streams"), kind: .youtube, logo: "fiawec.com", symbol: "flag.checkered"),
            Item(title: "Fórmula E", detail: "Carreras completas y resúmenes oficiales", url: channel("FIAFormulaE", "videos"), kind: .youtube, logo: "fiaformulae.com", symbol: "bolt.car"),
            Item(title: "Fórmula 1", detail: "Resúmenes oficiales de cada carrera", url: channel("Formula1", "videos"), kind: .youtube, logo: "formula1.com", symbol: "flag.checkered"),
            Item(title: "IndyCar", detail: "Resúmenes oficiales", url: channel("INDYCAR", "videos"), kind: .youtube, logo: "indycar.com", symbol: "flag.checkered"),
            Item(title: "NASCAR", detail: "Resúmenes oficiales", url: channel("NASCAR", "videos"), kind: .youtube, logo: "nascar.com", symbol: "flag.checkered"),
            Item(title: "MotoGP", detail: "Resúmenes oficiales", url: channel("MotoGP", "videos"), kind: .youtube, logo: "motogp.com", symbol: "flag.checkered"),
            Item(title: "WRC (Rally)", detail: "Resúmenes oficiales", url: channel("WRC", "videos"), kind: .youtube, logo: "wrc.com", symbol: "flag.checkered"),
            Item(title: "Carreras en vivo ahora", detail: "Búsqueda de transmisiones en vivo de automovilismo", url: liveSearch("GT World Challenge IMSA en vivo"), kind: .youtube, logo: "youtube.com", symbol: "dot.radiowaves.left.and.right", live: true),
        ]),
        Section(title: "Fútbol", note: "Los partidos completos del Campeonato chileno, Libertadores, MLS y ligas europeas son de pago (TNT Sports, ESPN, Apple TV, Disney+). Aquí están los resúmenes oficiales y los partidos que FIFA+ da gratis.", items: [
            Item(title: "FIFA+", detail: "Partidos en vivo gratis de algunas ligas y archivo de Mundiales", url: "https://www.plus.fifa.com/es/", kind: .web, logo: "fifa.com", symbol: "soccerball", live: true),
            Item(title: "Campeonato chileno", detail: "Resúmenes y goles de la fecha", url: search("resumen campeonato chileno TNT Sports"), kind: .youtube, logo: "anfp.cl", symbol: "soccerball"),
            Item(title: "CONMEBOL (Libertadores, Sudamericana)", detail: "Resúmenes oficiales", url: search("CONMEBOL resumen"), kind: .youtube, logo: "conmebol.com", symbol: "soccerball"),
            Item(title: "MLS", detail: "Resúmenes oficiales", url: channel("MLS", "videos"), kind: .youtube, logo: "mlssoccer.com", symbol: "soccerball"),
            Item(title: "LaLiga", detail: "Resúmenes oficiales", url: channel("LaLiga", "videos"), kind: .youtube, logo: "laliga.com", symbol: "soccerball"),
            Item(title: "Premier League", detail: "Resúmenes oficiales", url: channel("premierleague", "videos"), kind: .youtube, logo: "premierleague.com", symbol: "soccerball"),
            Item(title: "Serie A", detail: "Resúmenes oficiales", url: channel("SerieA", "videos"), kind: .youtube, logo: "legaseriea.it", symbol: "soccerball"),
            Item(title: "Bundesliga", detail: "Resúmenes oficiales", url: channel("bundesliga", "videos"), kind: .youtube, logo: "bundesliga.com", symbol: "soccerball"),
            Item(title: "Champions League", detail: "Resúmenes oficiales de la UEFA", url: search("UEFA Champions League resumen"), kind: .youtube, logo: "uefa.com", symbol: "soccerball"),
        ]),
        Section(title: "Películas y series", note: "Catálogos gratis y legales. Los que piden cuenta (Plex, ViX) son gratis igual.", items: [
            Item(title: "Pluto TV a pedido", detail: "Películas y series completas gratis", url: "https://pluto.tv/latam/on-demand", kind: .web, logo: "pluto.tv", symbol: "film"),
            Item(title: "Ondamedia", detail: "Cine chileno gratis (Ministerio de las Culturas)", url: "https://ondamedia.cl", kind: .web, logo: "ondamedia.cl", symbol: "film"),
            Item(title: "CNTV Play", detail: "Series y documentales chilenos gratis", url: "https://cntvplay.cl", kind: .web, logo: "cntvplay.cl", symbol: "film"),
            Item(title: "Plex: películas gratis", detail: "Miles de películas y series con anuncios", url: "https://watch.plex.tv", kind: .web, logo: "plex.tv", symbol: "film"),
            Item(title: "ViX (plan gratis)", detail: "Películas, series y novelas en español", url: "https://vix.com", kind: .web, logo: "vix.com", symbol: "film"),
            Item(title: "Tubi", detail: "Películas y series gratis (si está disponible en Chile)", url: "https://tubitv.com", kind: .web, logo: "tubitv.com", symbol: "film"),
            Item(title: "Clásicos de dominio público", detail: "Películas antiguas libres de derechos (Internet Archive)", url: "https://archive.org/details/feature_films", kind: .web, logo: "archive.org", symbol: "film.stack"),
        ]),
        Section(title: "Cortometrajes", note: nil, items: [
            Item(title: "Omeleto", detail: "Cortometrajes premiados", url: channel("Omeleto", "videos"), kind: .youtube, logo: "omeleto.com", symbol: "film.circle"),
            Item(title: "DUST", detail: "Cortos de ciencia ficción", url: channel("watchdust", "videos"), kind: .youtube, logo: "watchdust.com", symbol: "film.circle"),
            Item(title: "ALTER", detail: "Cortos de terror", url: channel("alter", "videos"), kind: .youtube, logo: "alter.com", symbol: "film.circle"),
            Item(title: "Cortos chilenos en Ondamedia", detail: "Cortometrajes nacionales gratis", url: "https://ondamedia.cl", kind: .web, logo: "ondamedia.cl", symbol: "film.circle"),
            Item(title: "Cortometrajes en español", detail: "Búsqueda en YouTube", url: search("cortometraje en español completo"), kind: .youtube, logo: "youtube.com", symbol: "magnifyingglass"),
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

