import SwiftUI
import UniformTypeIdentifiers

struct SettingsView: View {
    @ObservedObject var store: ChatStore
    @Environment(\.dismiss) private var dismiss
    @State private var profileImporter = false
    @State private var context = ""
    @State private var reply = ""
    private var proposed: GenerationSettings? {
        guard let c = Int(context), let r = Int(reply) else { return nil }
        return GenerationSettings(contextTokens: c, replyTokens: r)
    }
    private func refresh() {
        context = String(store.contextTokens)
        reply = String(store.replyTokens)
    }
    var body: some View {
        NavigationStack {
            Form {
                Section("Model") {
                    Text(store.model?.name ?? "No model loaded").font(.headline)
                    Text("Mimir runs on your device using its own chat template. No account or server is required.")
                        .font(.callout).foregroundStyle(.secondary)
                    Button("Import a Mimir GGUF…") { store.importer = true }.disabled(store.busy)
                    Button("Use bundled model", action: store.useBundledModel).disabled(store.busy)
                    Text("Profile: \(store.profile.name)")
                    Button("Import model profile…") { profileImporter = true }.disabled(store.busy || store.model == nil)
                }
                Section("Context and replies") {
                    TextField("Context tokens", text: $context)
                    TextField("Reply budget tokens", text: $reply)
                    Text("Active: \(store.contextTokens) context · \(store.replyTokens) reply tokens")
                        .font(.caption).foregroundStyle(.secondary)
                    if let error = proposed?.validationError(profile: store.profile) {
                        Text(error).font(.callout).foregroundStyle(.secondary)
                    } else if proposed == nil {
                        Text("Enter whole numbers for both limits.").font(.callout).foregroundStyle(.secondary)
                    }
                    if let trained = store.trainingContext {
                        Text("Model trained with a maximum context of \(trained) tokens. Longer contexts may reduce answer quality.")
                            .font(.callout).foregroundStyle(.secondary)
                    }
                    Button("Apply limits") {
                        if let proposed { store.applySettings(proposed) }
                    }.disabled(store.busy || proposed == nil || proposed?.validationError(profile: store.profile) != nil)
                    Button("Use memory-based defaults") {
                        store.useMemoryDefaults()
                    }.disabled(store.busy)
                    Text("The context includes the chat template, conversation and reserved reply budget. Changing context reloads the model. Automatic defaults use a memory estimate. Custom values override that estimate; large contexts may fail to load or cause the OS to close the app.")
                        .font(.callout).foregroundStyle(.secondary)
                    Text("Completed chats stay on this device. Stopping a reply returns your message to the composer.")
                        .font(.callout).foregroundStyle(.secondary)
                    if let notice = store.notice {
                        Text(notice).font(.callout).foregroundStyle(.secondary)
                    }
                }.disabled(store.busy)
                Section("Conversation compaction") {
                    Toggle("Automatically summarize older turns", isOn: Binding(
                        get: { store.compactionSettings.enabled },
                        set: { store.setCompaction(enabled: $0) }))
                    Toggle("Show compaction summary", isOn: Binding(
                        get: { store.compactionSettings.showSummary },
                        set: { store.setCompaction(showSummary: $0) }))
                    Text("Summaries make room for new messages. Your full transcript stays saved. Turning compaction off sends the full transcript, which may exceed the context limit.")
                        .font(.callout).foregroundStyle(.secondary)
                }.disabled(store.busy)
                Section("About") {
                    HStack(spacing: 12) {
                        MimirMark(size: 48)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(MimirBrand.name).font(.headline)
                            Text("MVP 0.1").foregroundStyle(.secondary)
                        }
                    }
                    FoundationModelsLogo(width: 200)
                    NavigationLink("Model license · Apache 2.0") { LicenseView(resource: "DFM-Mimir-LICENSE", title: "Model license") }
                    NavigationLink("llama.cpp license · MIT") { LicenseView(resource: "llama-LICENSE", title: "llama.cpp") }
                    NavigationLink("Mimir code license · MIT") { LicenseView(resource: "Mimir-LICENSE", title: "Mimir code") }
                }
            }.formStyle(.grouped).navigationTitle("DFM Mimir settings")
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
                .fileImporter(isPresented: $store.importer, allowedContentTypes: [.data]) { result in
                    switch result {
                    case .success(let url): store.importModel(url); dismiss()
                    case .failure(let error): store.notice = error.localizedDescription
                    }
                }
        }
        .fileImporter(isPresented: $profileImporter, allowedContentTypes: [.json]) { result in
            switch result {
            case .success(let url): store.importProfile(url)
            case .failure(let error): store.notice = error.localizedDescription
            }
        }
        .onAppear(perform: refresh)
        .onChange(of: store.generationSettings) { _, _ in refresh() }
        .frame(minWidth: 340, idealWidth: 480, minHeight: 450)
    }
}

private struct LicenseView: View {
    let resource: String
    let title: String
    var body: some View {
        ScrollView {
            Text(Bundle.main.url(forResource: resource, withExtension: "txt")
                .flatMap { try? String(contentsOf: $0, encoding: .utf8) } ?? "License unavailable.")
                .font(.system(.caption, design: .monospaced)).textSelection(.enabled).padding(20)
        }.navigationTitle(title)
    }
}
