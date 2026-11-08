import AVFoundation
import UIKit

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        // Categoría "playback": el audio suena con el interruptor de silencio activado y sigue en segundo plano.
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .moviePlayback)
        AdBlocker.shared.prepare()
        return true
    }

    func application(_ application: UIApplication, configurationForConnecting session: UISceneSession,
                     options: UIScene.ConnectionOptions) -> UISceneConfiguration {
        UISceneConfiguration(name: "Default", sessionRole: session.role)
    }
}

final class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let scene = scene as? UIWindowScene else { return }
        let window = UIWindow(windowScene: scene)
        window.rootViewController = WebViewController()
        window.overrideUserInterfaceStyle = .dark
        window.makeKeyAndVisible()
        self.window = window
        if connectionOptions.shortcutItem?.type == Self.freeTVShortcut { root?.openFreeTVFromShortcut() }
    }

    static let freeTVShortcut = "cl.eleva.tvweb.tvgratis"
    private var root: WebViewController? { window?.rootViewController as? WebViewController }

    /// Mantener el ícono de edutube → "TV gratis".
    func windowScene(_ windowScene: UIWindowScene, performActionFor shortcutItem: UIApplicationShortcutItem,
                     completionHandler: @escaping (Bool) -> Void) {
        let ok = shortcutItem.type == Self.freeTVShortcut
        if ok { root?.openFreeTVFromShortcut() }
        completionHandler(ok)
    }

    func sceneDidEnterBackground(_ scene: UIScene) {
        (window?.rootViewController as? WebViewController)?.didEnterBackground()
    }

    func sceneWillEnterForeground(_ scene: UIScene) {
        (window?.rootViewController as? WebViewController)?.willEnterForeground()
    }
}
