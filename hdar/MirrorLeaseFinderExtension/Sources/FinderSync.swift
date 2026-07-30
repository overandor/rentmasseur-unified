import Cocoa
import FinderSync

@objc(MirrorLeaseFinderSync)
final class MirrorLeaseFinderSync: FIFinderSync {
    override init() {
        super.init()
        let home = FileManager.default.homeDirectoryForCurrentUser
        let folders = ["Desktop", "Documents", "Downloads"].map {
            home.appendingPathComponent($0, isDirectory: true)
        }.filter { FileManager.default.fileExists(atPath: $0.path) }
        FIFinderSyncController.default().directoryURLs = Set(folders)
    }

    override func menu(for menuKind: FIMenuKind) -> NSMenu? {
        guard menuKind == .contextualMenuForItems else {
            return nil
        }
        let menu = NSMenu(title: "MirrorLease")
        let item = NSMenuItem(
            title: "Share with AI — MirrorLease",
            action: #selector(shareSelectedFiles),
            keyEquivalent: ""
        )
        item.target = self
        menu.addItem(item)
        return menu
    }

    @objc private func shareSelectedFiles() {
        guard let urls = FIFinderSyncController.default().selectedItemURLs() else { return }
        let filePaths = urls.filter { !$0.hasDirectoryPath }.map { $0.path }
        guard !filePaths.isEmpty else { return }

        let appURL = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        let configuration = NSWorkspace.OpenConfiguration()
        configuration.activates = true
        configuration.arguments = filePaths
        NSWorkspace.shared.openApplication(at: appURL, configuration: configuration) { _, error in
            if let error {
                NSLog("MirrorLease host launch failed: %@", error.localizedDescription)
            }
        }
    }
}
