import SwiftUI
import AppKit

@MainActor
final class PushStore: ObservableObject {
    @Published var articles: [Article] = []
    @Published var host = ""
    @Published var manualHost = ""
    @Published var connected = false
    @Published var busy = false
    @Published var activity = "正在检查连接…"
    @Published var notice = ""
    @Published var isError = false
    @Published var showPicker = false
    @Published var showManual = false
    @Published var completed = 0
    @Published var total = 0
    private var started = false

    init() {
        if let data = UserDefaults.standard.data(forKey: "articles"),
           let saved = try? JSONDecoder().decode([Article].self, from: data) {
            articles = saved.map { item in
                var item = item
                if item.status == "发送中" { item.status = "等待发送" }
                return item
            }
        }
    }

    var pendingCount: Int { articles.filter { $0.status != "已发送" }.count }

    func save() {
        if let data = try? JSONEncoder().encode(articles) { UserDefaults.standard.set(data, forKey: "articles") }
    }

    func add(_ urls: [URL]) {
        guard !busy else { return }
        var rejected = 0
        for url in urls {
            guard url.isFileURL, ["md", "markdown", "epub"].contains(url.pathExtension.lowercased()) else {
                rejected += 1; continue
            }
            let path = url.standardizedFileURL.path
            if let index = articles.firstIndex(where: { $0.path == path }) {
                articles[index].status = "等待发送"
                articles[index].details = ""
            } else { articles.append(Article(path: path)) }
        }
        if rejected > 0 { notice = "已略过 \(rejected) 个不支持的文件。请选择 Markdown 或 EPUB。"; isError = true }
        else { notice = ""; isError = false }
        save()
    }

    func remove(_ id: UUID) { guard !busy else { return }; articles.removeAll { $0.id == id }; save() }
    func clearSent() { guard !busy else { return }; articles.removeAll { $0.status == "已发送" }; save() }
    func retry(_ id: UUID) {
        guard !busy, let index = articles.firstIndex(where: { $0.id == id }) else { return }
        articles[index].status = "等待发送"; articles[index].details = ""; save()
    }

    func start() async {
        guard !started else { return }; started = true
        busy = true
        let status = await Bridge.call(["status"])
        if status.ok {
            host = status.host ?? ""; manualHost = host
            await findConnection(manual: false)
        } else { present(status) }
        busy = false
    }

    func connect(manual: Bool = false) async {
        guard !busy else { return }
        busy = true; notice = ""; isError = false
        await findConnection(manual: manual)
        busy = false
    }

    private func findConnection(manual: Bool) async {
        connected = false
        activity = manual ? "正在连接 Kindle…" : "正在寻找你的 Kindle…"
        let response = await Bridge.call(manual ? ["connect", manualHost.trimmingCharacters(in: .whitespacesAndNewlines)] : ["discover"])
        if response.ok {
            host = response.host ?? ""; manualHost = host; connected = true
            activity = "Kindle 已连接"
        } else { present(response); activity = "Kindle 尚未连接" }
    }

    private func present(_ response: BridgeResponse) {
        isError = !response.ok
        notice = response.message ?? "操作未完成，请重试。"
        if !response.ok { activity = "需要检查连接" }
    }

    func send() async {
        guard !busy, pendingCount > 0 else { return }
        busy = true; notice = ""; isError = false; completed = 0
        let ids = articles.filter { $0.status != "已发送" }.map(\.id)
        total = ids.count
        // Revalidate every time; recover automatically after a Wi-Fi change.
        await findConnection(manual: false)
        guard connected else { busy = false; return }
        var failures = 0
        for id in ids {
            guard let index = articles.firstIndex(where: { $0.id == id }) else { continue }
            articles[index].status = "发送中"
            activity = "正在发送 \(completed + 1) / \(total)：\(articles[index].title)"
            let response = await Bridge.call(["send", host, articles[index].path])
            articles[index].status = response.ok ? "已发送" : "失败"
            articles[index].details = response.ok ? (response.details?.contains("提示：") == true ? response.details! : "已读回文件，校验一致") : (response.message ?? "发送失败")
            articles[index].output = response.output
            if !response.ok { failures += 1 }
            completed += 1; save()
        }
        isError = failures > 0
        notice = failures == 0 ? "\(total) 篇文章已送达。Kindle → 文件浏览器 → documents → 我的文章。" : "\(total - failures) 篇已送达，\(failures) 篇未完成。可以重试未完成的文章。"
        activity = failures == 0 ? "发送完成" : "部分文章未完成"
        busy = false
    }

    func revealOutput() {
        let url = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Documents/Kindle推送/已转换")
        try? FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        NSWorkspace.shared.open(url)
    }
}
