import UIKit

/// Pantalla "TV gratis": una fila de íconos con logo por sección, como en las apps de streaming.
final class FreeTVViewController: UICollectionViewController {
    var onOpen: ((FreeTV.Item) -> Void)?
    var onMirror: (() -> Void)?
    var onRemote: (() -> Void)?

    private let sections = FreeTV.sections

    init() { super.init(collectionViewLayout: Self.layout()) }
    required init?(coder: NSCoder) { fatalError() }

    private static func layout() -> UICollectionViewLayout {
        UICollectionViewCompositionalLayout { section, _ in
            if section == 0 { // texto de introducción
                let size = NSCollectionLayoutSize(widthDimension: .fractionalWidth(1), heightDimension: .estimated(80))
                let s = NSCollectionLayoutSection(group: .horizontal(layoutSize: size, subitems: [NSCollectionLayoutItem(layoutSize: size)]))
                s.contentInsets = NSDirectionalEdgeInsets(top: 4, leading: 20, bottom: 8, trailing: 20)
                return s
            }
            let item = NSCollectionLayoutItem(layoutSize: NSCollectionLayoutSize(widthDimension: .fractionalWidth(1), heightDimension: .fractionalHeight(1)))
            let group = NSCollectionLayoutGroup.horizontal(
                layoutSize: NSCollectionLayoutSize(widthDimension: .absolute(108), heightDimension: .absolute(150)), subitems: [item])
            let s = NSCollectionLayoutSection(group: group)
            s.orthogonalScrollingBehavior = .continuous
            s.interGroupSpacing = 12
            s.contentInsets = NSDirectionalEdgeInsets(top: 6, leading: 20, bottom: 6, trailing: 20)
            let header = NSCollectionLayoutBoundarySupplementaryItem(
                layoutSize: NSCollectionLayoutSize(widthDimension: .fractionalWidth(1), heightDimension: .estimated(34)),
                elementKind: UICollectionView.elementKindSectionHeader, alignment: .top)
            let footer = NSCollectionLayoutBoundarySupplementaryItem(
                layoutSize: NSCollectionLayoutSize(widthDimension: .fractionalWidth(1), heightDimension: .estimated(30)),
                elementKind: UICollectionView.elementKindSectionFooter, alignment: .bottom)
            s.boundarySupplementaryItems = [header, footer]
            return s
        }
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "TV gratis"
        collectionView.backgroundColor = UIColor(white: 0.06, alpha: 1)
        navigationItem.leftBarButtonItem = UIBarButtonItem(title: "YouTube", style: .plain, target: self, action: #selector(close))
        var right = [UIBarButtonItem(image: UIImage(systemName: "rectangle.on.rectangle"), style: .plain,
                                     target: self, action: #selector(mirror))]
        right[0].accessibilityLabel = "Espejo de pantalla en la TV"
        if Remote.target != nil {
            let r = UIBarButtonItem(image: UIImage(systemName: "playpause.fill"), style: .plain, target: self, action: #selector(remote))
            r.accessibilityLabel = "Control remoto de la TV"
            right.append(r)
        }
        navigationItem.rightBarButtonItems = right
        collectionView.register(TileCell.self, forCellWithReuseIdentifier: "tile")
        collectionView.register(IntroCell.self, forCellWithReuseIdentifier: "intro")
        collectionView.register(TextView.self, forSupplementaryViewOfKind: UICollectionView.elementKindSectionHeader, withReuseIdentifier: "h")
        collectionView.register(TextView.self, forSupplementaryViewOfKind: UICollectionView.elementKindSectionFooter, withReuseIdentifier: "f")
        Chromecast.shared.startDiscovery()
    }

    @objc private func close() { dismiss(animated: true) }
    @objc private func mirror() { dismiss(animated: true) { [onMirror] in onMirror?() } }
    @objc private func remote() { dismiss(animated: true) { [onRemote] in onRemote?() } }

    override func numberOfSections(in collectionView: UICollectionView) -> Int { sections.count + 1 }

    override func collectionView(_ collectionView: UICollectionView, numberOfItemsInSection section: Int) -> Int {
        section == 0 ? 1 : sections[section - 1].items.count
    }

    override func collectionView(_ collectionView: UICollectionView, cellForItemAt indexPath: IndexPath) -> UICollectionViewCell {
        if indexPath.section == 0 {
            return collectionView.dequeueReusableCell(withReuseIdentifier: "intro", for: indexPath)
        }
        let cell = collectionView.dequeueReusableCell(withReuseIdentifier: "tile", for: indexPath) as! TileCell
        cell.show(sections[indexPath.section - 1].items[indexPath.item])
        return cell
    }

    override func collectionView(_ collectionView: UICollectionView, viewForSupplementaryElementOfKind kind: String,
                                 at indexPath: IndexPath) -> UICollectionReusableView {
        let header = kind == UICollectionView.elementKindSectionHeader
        let v = collectionView.dequeueReusableSupplementaryView(ofKind: kind, withReuseIdentifier: header ? "h" : "f", for: indexPath) as! TextView
        let section = sections[indexPath.section - 1]
        v.set(header ? section.title : (section.note ?? ""), header: header)
        return v
    }

    override func collectionView(_ collectionView: UICollectionView, didSelectItemAt indexPath: IndexPath) {
        guard indexPath.section > 0 else { return }
        let item = sections[indexPath.section - 1].items[indexPath.item]
        dismiss(animated: true) { [onOpen] in onOpen?(item) }
    }
}

// MARK: - Celdas

private final class TileCell: UICollectionViewCell {
    private let box = UIView()
    private let logo = UIImageView()
    private let initials = UILabel()
    private let name = UILabel()
    private let badge = UILabel()
    private var domain = ""

    override init(frame: CGRect) {
        super.init(frame: frame)
        box.layer.cornerRadius = 22
        box.clipsToBounds = true
        logo.contentMode = .scaleAspectFit
        initials.font = .systemFont(ofSize: 30, weight: .heavy)
        initials.textColor = .white
        initials.textAlignment = .center
        initials.adjustsFontSizeToFitWidth = true
        name.font = .systemFont(ofSize: 12, weight: .semibold)
        name.textColor = .white
        name.numberOfLines = 2
        name.textAlignment = .center
        badge.text = " EN VIVO "
        badge.font = .systemFont(ofSize: 9, weight: .heavy)
        badge.textColor = .white
        badge.backgroundColor = UIColor(red: 1, green: 59 / 255, blue: 48 / 255, alpha: 1)
        badge.layer.cornerRadius = 4
        badge.clipsToBounds = true
        for v in [box, logo, initials, name, badge] { v.translatesAutoresizingMaskIntoConstraints = false }
        contentView.addSubview(box)
        box.addSubview(initials)
        box.addSubview(logo)
        contentView.addSubview(name)
        contentView.addSubview(badge)
        NSLayoutConstraint.activate([
            box.topAnchor.constraint(equalTo: contentView.topAnchor),
            box.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            box.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
            box.heightAnchor.constraint(equalTo: box.widthAnchor),
            logo.centerXAnchor.constraint(equalTo: box.centerXAnchor),
            logo.centerYAnchor.constraint(equalTo: box.centerYAnchor),
            logo.widthAnchor.constraint(equalTo: box.widthAnchor, multiplier: 0.62),
            logo.heightAnchor.constraint(equalTo: box.heightAnchor, multiplier: 0.62),
            initials.leadingAnchor.constraint(equalTo: box.leadingAnchor, constant: 8),
            initials.trailingAnchor.constraint(equalTo: box.trailingAnchor, constant: -8),
            initials.centerYAnchor.constraint(equalTo: box.centerYAnchor),
            badge.topAnchor.constraint(equalTo: box.topAnchor, constant: 7),
            badge.trailingAnchor.constraint(equalTo: box.trailingAnchor, constant: -7),
            name.topAnchor.constraint(equalTo: box.bottomAnchor, constant: 6),
            name.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            name.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError() }

    func show(_ item: FreeTV.Item) {
        domain = item.logo
        name.text = item.title
        badge.isHidden = !item.live
        accessibilityLabel = item.title + (item.live ? ", en vivo" : "") + ". " + item.detail
        isAccessibilityElement = true
        let color = Self.color(for: item.logo)
        box.backgroundColor = color
        initials.text = Self.initials(item.title)
        initials.isHidden = false
        logo.image = nil
        Logos.shared.image(for: item.logo) { [weak self] image in
            guard let self = self, self.domain == item.logo, let image = image else { return }
            self.logo.image = image
            self.initials.isHidden = true
            self.box.backgroundColor = .white
        }
    }

    override var isHighlighted: Bool {
        didSet { UIView.animate(withDuration: 0.12) { self.transform = self.isHighlighted ? CGAffineTransform(scaleX: 0.94, y: 0.94) : .identity } }
    }

    private static func initials(_ title: String) -> String {
        let clean = title.components(separatedBy: CharacterSet(charactersIn: "(:")).first ?? title
        let words = clean.split(separator: " ").filter { $0.first?.isLetter == true || $0.first?.isNumber == true }
        if let w = words.first, words.count == 1 || w.count <= 4 { return String(w.prefix(4)).uppercased() }
        return words.prefix(2).compactMap { $0.first.map(String.init) }.joined().uppercased()
    }

    private static func color(for key: String) -> UIColor {
        let hue = CGFloat(key.unicodeScalars.reduce(0) { ($0 * 31 + Int($1.value)) % 360 }) / 360
        return UIColor(hue: hue, saturation: 0.55, brightness: 0.45, alpha: 1)
    }
}

private final class IntroCell: UICollectionViewCell {
    override init(frame: CGRect) {
        super.init(frame: frame)
        let label = UILabel()
        label.numberOfLines = 0
        label.font = .preferredFont(forTextStyle: .footnote)
        label.textColor = .secondaryLabel
        label.text = "Solo fuentes oficiales, legales y gratuitas. Todo va al Chromecast con el botón rojo, y mientras se "
            + "ve en la TV aparece el control remoto (pausa, adelantar, volumen, subtítulos, audio). Si una página no deja "
            + "enviar su video, usa el espejo de pantalla (arriba a la derecha).\n\nOjo: la mayoría de los partidos y "
            + "carreras completos en vivo son de pago; aquí está lo que las ligas y canales dan gratis."
        label.translatesAutoresizingMaskIntoConstraints = false
        contentView.addSubview(label)
        NSLayoutConstraint.activate([
            label.topAnchor.constraint(equalTo: contentView.topAnchor),
            label.bottomAnchor.constraint(equalTo: contentView.bottomAnchor),
            label.leadingAnchor.constraint(equalTo: contentView.leadingAnchor),
            label.trailingAnchor.constraint(equalTo: contentView.trailingAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError() }
}

private final class TextView: UICollectionReusableView {
    private let label = UILabel()

    override init(frame: CGRect) {
        super.init(frame: frame)
        label.numberOfLines = 0
        label.translatesAutoresizingMaskIntoConstraints = false
        addSubview(label)
        NSLayoutConstraint.activate([
            label.topAnchor.constraint(equalTo: topAnchor, constant: 6),
            label.bottomAnchor.constraint(equalTo: bottomAnchor, constant: -4),
            label.leadingAnchor.constraint(equalTo: leadingAnchor),
            label.trailingAnchor.constraint(equalTo: trailingAnchor),
        ])
    }

    required init?(coder: NSCoder) { fatalError() }

    func set(_ text: String, header: Bool) {
        label.text = text
        label.font = header ? .systemFont(ofSize: 20, weight: .bold) : .preferredFont(forTextStyle: .caption1)
        label.textColor = header ? .white : .secondaryLabel
    }
}

// MARK: - Logos

/**
 Descarga el ícono oficial de cada sitio (el "apple-touch-icon" que los sitios publican para la pantalla de
 inicio; si no hay, el de Google) y lo guarda en el iPhone para no volver a pedirlo.
 */
final class Logos {
    static let shared = Logos()

    private let memory = NSCache<NSString, UIImage>()
    private var waiting: [String: [(UIImage?) -> Void]] = [:]
    private let folder: URL = {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0].appendingPathComponent("logos")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }()

    func image(for domain: String, completion: @escaping (UIImage?) -> Void) {
        if let img = memory.object(forKey: domain as NSString) { return completion(img) }
        let file = folder.appendingPathComponent(domain + ".png")
        if let data = try? Data(contentsOf: file), let img = UIImage(data: data) {
            memory.setObject(img, forKey: domain as NSString)
            return completion(img)
        }
        if waiting[domain] != nil { waiting[domain]?.append(completion); return }
        waiting[domain] = [completion]
        let candidates = [
            "https://www.\(domain)/apple-touch-icon.png",
            "https://\(domain)/apple-touch-icon.png",
            "https://www.google.com/s2/favicons?domain=\(domain)&sz=256",
        ]
        fetch(candidates) { [weak self] data, img in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if let img = img, let data = data {
                    self.memory.setObject(img, forKey: domain as NSString)
                    try? data.write(to: file)
                }
                self.waiting.removeValue(forKey: domain)?.forEach { $0(img) }
            }
        }
    }

    private func fetch(_ urls: [String], completion: @escaping (Data?, UIImage?) -> Void) {
        guard let first = urls.first, let url = URL(string: first) else { return completion(nil, nil) }
        URLSession.shared.dataTask(with: URLRequest(url: url, timeoutInterval: 8)) { data, resp, _ in
            let ok = ((resp as? HTTPURLResponse)?.statusCode ?? 0) == 200
            // Se descartan los íconos diminutos (se verían borrosos) y el globo genérico de Google.
            if ok, let data = data, let img = UIImage(data: data), img.size.width * img.scale >= 48 {
                return completion(data, img)
            }
            self.fetch(Array(urls.dropFirst()), completion: completion)
        }.resume()
    }
}
