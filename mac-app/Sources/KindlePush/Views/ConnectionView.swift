import SwiftUI

struct ConnectionView: View {
    @ObservedObject var store: PushStore
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 12) {
                Image(systemName: "ipad.gen1")
                    .font(.system(size: 27)).foregroundStyle(store.connected ? Color.accentColor : Color.secondary)
                VStack(alignment: .leading, spacing: 3) {
                    HStack(spacing: 6) {
                        Circle().fill(store.connected ? Color.green : Color.secondary.opacity(0.5)).frame(width: 7, height: 7)
                        Text(store.connected ? "我的 Kindle" : "等待 Kindle").fontWeight(.semibold)
                    }
                    Text(store.connected ? "已连接 · \(store.host)" : "打开 KOReader，并连接同一个 Wi-Fi")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Button("自动寻找", systemImage: "arrow.clockwise") { Task { await store.connect() } }
                    .disabled(store.busy)
            }
            DisclosureGroup("手动连接", isExpanded: $store.showManual) {
                HStack {
                    TextField("Kindle IP，例如 192.168.1.42", text: $store.manualHost)
                        .textFieldStyle(.roundedBorder)
                        .onSubmit { Task { await store.connect(manual: true) } }
                    Button("连接") { Task { await store.connect(manual: true) } }
                }
                .disabled(store.busy).padding(.top, 6)
                Text("换网络后先点自动寻找；若网络隔离设备，请换到可互通的 Wi-Fi。")
                    .font(.caption).foregroundStyle(.secondary).padding(.top, 4)
            }
            .font(.caption).foregroundStyle(.secondary)
        }
        .padding(18).background(.quaternary.opacity(0.4), in: RoundedRectangle(cornerRadius: 14))
    }
}
