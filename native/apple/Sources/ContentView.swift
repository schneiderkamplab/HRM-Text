import SwiftUI
import UniformTypeIdentifiers
#if os(macOS)
import AppKit
#endif

struct ContentView: View {
    @ObservedObject var store: ChatStore
    @Environment(\.scenePhase) private var scenePhase
    @FocusState private var composerFocused: Bool
    @State private var deleting = false
    @State private var compactColumn: NavigationSplitViewColumn = .detail
    var body: some View {
        NavigationSplitView(preferredCompactColumn: $compactColumn) {
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 10) {
                    MimirMark(size: 38)
                    Text(MimirBrand.name).font(.system(size: 24, weight: .semibold))
                }.padding(.horizontal, 20).padding(.top, 22)
                Button(action: newChat) {
                    Label("New chat", systemImage: "square.and.pencil").frame(maxWidth: .infinity, alignment: .leading)
                }.buttonStyle(.bordered).controlSize(.large).padding(.horizontal, 16).disabled(store.busy)
                Text("YOUR CONVERSATIONS").font(.caption2.weight(.semibold)).foregroundStyle(.secondary).padding(.horizontal, 20)
                List(selection: Binding(get: { store.selected }, set: { if let id = $0 { store.select(id) } })) {
                    ForEach(store.saved.conversations) { chat in
                        NavigationLink(value: chat.id) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text(chat.title).lineLimit(1)
                                Text(chat.updated, style: .date).font(.caption).foregroundStyle(.secondary)
                            }.padding(.vertical, 5)
                        }
                    }
                }.listStyle(.sidebar).disabled(store.busy)
                Label("Private. Local. Yours.", systemImage: "lock.shield")
                    .font(.caption).foregroundStyle(.secondary).padding(20)
            }.navigationTitle("").navigationSplitViewColumnWidth(min: 220, ideal: 260)
        } detail: {
            VStack(spacing: 0) {
                HStack {
                    Circle().fill(store.ready ? Color.green : Color.orange).frame(width: 7, height: 7)
                    Text(store.loading ? "Loading DFM Mimir…" : (store.ready ? store.engineLabel : "Choose a model to begin"))
                        .font(.caption).foregroundStyle(.secondary)
                    Spacer()
                    if store.loading { ProgressView().controlSize(.small) }
                }.padding(.horizontal, 24).padding(.vertical, 12)
                Divider()
                if store.messages.isEmpty && store.pendingPrompt == nil {
                    ScrollView {
                        welcome.frame(maxWidth: .infinity)
                    }
                    .scrollDismissesKeyboard(.interactively)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ScrollViewReader { reader in
                        ScrollView {
                            LazyVStack(alignment: .leading, spacing: 28) {
                                ForEach(store.messages) { message in messageView(message.role, message.content) }
                                if let prompt = store.pendingPrompt {
                                    messageView("user", prompt)
                                    if store.streaming.isEmpty {
                                        HStack { ProgressView().controlSize(.small); Text("DFM Mimir is thinking…").foregroundStyle(.secondary) }
                                    } else { messageView("assistant", store.streaming) }
                                }
                                Color.clear.frame(height: 1).id("bottom")
                            }.padding(24).frame(maxWidth: 780).frame(maxWidth: .infinity)
                        }
                        .scrollDismissesKeyboard(.interactively)
                        .onChange(of: store.streaming) { _, _ in reader.scrollTo("bottom", anchor: .bottom) }
                        .onChange(of: store.pendingPrompt) { _, _ in reader.scrollTo("bottom", anchor: .bottom) }
                        .onChange(of: store.messages.count) { _, _ in reader.scrollTo("bottom", anchor: .bottom) }
                    }
                }
                if let notice = store.notice {
                    HStack(alignment: .top) {
                        Text(notice).font(.callout).foregroundStyle(.secondary)
                        Spacer(minLength: 8)
                        Button { store.notice = nil } label: { Image(systemName: "xmark") }
                            .buttonStyle(.plain).accessibilityLabel("Dismiss message")
                    }.padding(.horizontal, 24).padding(.bottom, 10)
                }
                if !store.modelMatches {
                    Text("This chat belongs to a different model. Load that model or start a new chat.")
                        .font(.callout).foregroundStyle(.secondary).padding(.horizontal, 24)
                }
            }
            .safeAreaInset(edge: .bottom, spacing: 0) {
                composer.background(.background)
            }
            .navigationTitle(store.active?.title ?? MimirBrand.name)
            .toolbar {
                ToolbarItemGroup(placement: .primaryAction) {
                    Button(action: newChat) { Image(systemName: "square.and.pencil") }
                        .accessibilityLabel("New chat").disabled(store.busy)
                    Button { store.showingSettings = true } label: { Image(systemName: "slider.horizontal.3") }
                        .accessibilityLabel("Model and settings")
                    if store.active != nil {
                        Menu {
                            if !store.messages.isEmpty {
                                ShareLink(item: store.messages.map { "\($0.role == "user" ? "You" : MimirBrand.name)\n\($0.content)" }.joined(separator: "\n\n")) {
                                    Label("Share conversation", systemImage: "square.and.arrow.up")
                                }
                            }
                            Button("Delete conversation", role: .destructive) { deleting = true }.disabled(store.busy)
                        } label: { Image(systemName: "ellipsis.circle") }
                    }
                }
            }
        }
        .sheet(isPresented: $store.showingSettings) { SettingsView(store: store) }
        .confirmationDialog("Delete this conversation?", isPresented: $deleting, titleVisibility: .visible) {
            Button("Delete", role: .destructive, action: store.deleteActive)
        }
        .onChange(of: scenePhase) { _, phase in if phase == .background { store.stop() } }
    }
    private func newChat() {
        composerFocused = false
        store.newChat()
        compactColumn = .detail
    }
    private func send() {
        guard store.canSend else { return }
        composerFocused = false
        store.send()
    }
    private var welcome: some View {
        VStack(spacing: 20) {
            MimirMark(size: 88)
            Text(MimirBrand.name).font(.system(size: 34, weight: .semibold)).multilineTextAlignment(.center)
            Text("Ask, explore, or find the right words.\nYour conversation stays on this device.")
                .foregroundStyle(.secondary).multilineTextAlignment(.center)
            FoundationModelsLogo(width: 170)
            VStack(spacing: 10) {
                suggestion("Forklar noget enkelt", prompt: "Forklar forskellen mellem vejr og klima kort.")
                suggestion("Help me find the words", prompt: "Help me write a short, friendly thank-you note.")
                suggestion("Explore an idea", prompt: "Suggest three creative things to do on a rainy afternoon.")
            }.padding(.top, 10).frame(maxWidth: 340)
        }.padding(28)
    }
    private func suggestion(_ title: String, prompt: String) -> some View {
        Button { store.draft = prompt } label: {
            HStack { Text(title); Spacer(); Image(systemName: "arrow.up.left") }
                .padding(13).background(.quaternary.opacity(0.5), in: RoundedRectangle(cornerRadius: 12))
        }.buttonStyle(.plain).disabled(store.busy)
    }
    private func messageView(_ role: String, _ content: String) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 6) {
                if role == "assistant" {
                    MimirMark(size: 20).accessibilityHidden(true)
                }
                Text(role == "user" ? "YOU" : "DFM MIMIR")
                    .font(.caption2.weight(.bold)).foregroundStyle(.secondary)
            }
            Text(content).font(.body).textSelection(.enabled).lineSpacing(5)
                .frame(maxWidth: .infinity, alignment: .leading)
        }.padding(role == "user" ? 18 : 0)
            .background(role == "user" ? MimirBrand.accent.opacity(0.07) : .clear, in: RoundedRectangle(cornerRadius: 16))
    }
    private var composer: some View {
        VStack(spacing: 9) {
            #if os(iOS)
            if composerFocused {
                HStack {
                    Spacer()
                    Button("Done", systemImage: "keyboard.chevron.compact.down") {
                        composerFocused = false
                    }
                    .accessibilityLabel("Dismiss keyboard")
                }
            }
            #endif
            HStack(alignment: .bottom, spacing: 12) {
                TextField("Message DFM Mimir…", text: $store.draft, axis: .vertical)
                    .textFieldStyle(.plain).lineLimit(1...5).padding(12)
                    .focused($composerFocused)
                    .disabled(store.generating)
                    #if os(macOS)
                    .onKeyPress(.return, phases: .down) { press in
                        // Let the text system finish IME composition and insert modified newlines.
                        if let editor = NSApp.keyWindow?.firstResponder as? NSTextView,
                           editor.hasMarkedText() { return .ignored }
                        if press.modifiers.contains(.shift) {
                            if let editor = NSApp.keyWindow?.firstResponder as? NSTextView {
                                editor.insertNewlineIgnoringFieldEditor(nil)
                                return .handled
                            }
                            return .ignored
                        }
                        if !press.modifiers.intersection([.option, .control]).isEmpty {
                            return .ignored
                        }
                        send()
                        return .handled
                    }
                    #endif
                if store.generating {
                    Button(action: store.stop) { Image(systemName: "stop.fill").frame(width: 26, height: 26) }
                        .buttonStyle(.borderedProminent).accessibilityLabel("Stop reply").padding(6)
                } else {
                    Button(action: send) { Image(systemName: "arrow.up").fontWeight(.semibold).frame(width: 26, height: 26) }
                        .buttonStyle(.borderedProminent).disabled(!store.canSend).accessibilityLabel("Send message")
                        #if os(macOS)
                        .keyboardShortcut(.return, modifiers: .command)
                        .help("Send (Return or ⌘Return). Shift+Return adds a new line.")
                        #endif
                        .padding(6)
                }
            }.background(.background, in: RoundedRectangle(cornerRadius: 18))
                .overlay(RoundedRectangle(cornerRadius: 18).stroke(.primary.opacity(0.12)))
            Text("DFM Mimir can make mistakes. Check important details.").font(.caption2).foregroundStyle(.secondary)
        }.padding(.horizontal, 24).padding(.top, 14).padding(.bottom, 16).frame(maxWidth: 820).frame(maxWidth: .infinity)
    }
}
