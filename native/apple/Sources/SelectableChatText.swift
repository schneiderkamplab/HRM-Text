import SwiftUI

#if os(macOS)
/// Native selection avoids SwiftUI's SelectionOverlay layout loop inside scrolling chat rows.
struct SelectableChatText: NSViewRepresentable {
    let text: String
    var compact = false

    func makeNSView(context: Context) -> NSTextView {
        let view = NSTextView()
        view.isEditable = false
        view.isSelectable = true
        view.isRichText = false
        view.drawsBackground = false
        view.textContainerInset = .zero
        view.textContainer?.lineFragmentPadding = 0
        view.textContainer?.widthTracksTextView = true
        view.isHorizontallyResizable = false
        view.isVerticallyResizable = true
        view.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        return view
    }

    func updateNSView(_ view: NSTextView, context: Context) {
        let font = NSFont.preferredFont(forTextStyle: compact ? .callout : .body)
        // Do not reset selection or invalidate layout when only scroll position changes.
        if view.string != text || view.font != font {
            let paragraph = NSMutableParagraphStyle()
            paragraph.lineSpacing = compact ? 0 : 5
            view.textStorage?.setAttributedString(NSAttributedString(string: text, attributes: [
                .font: font, .foregroundColor: NSColor.labelColor, .paragraphStyle: paragraph
            ]))
        }
    }

    func sizeThatFits(_ proposal: ProposedViewSize, nsView: NSTextView, context: Context) -> CGSize? {
        guard let width = proposal.width, width.isFinite, width > 0,
              let container = nsView.textContainer, let layout = nsView.layoutManager else { return nil }
        let size = NSSize(width: width, height: .greatestFiniteMagnitude)
        if container.containerSize != size { container.containerSize = size }
        layout.ensureLayout(for: container)
        return CGSize(width: width, height: max(1, ceil(layout.usedRect(for: container).height)))
    }
}
#else
struct SelectableChatText: View {
    let text: String
    var compact = false
    var body: some View {
        Text(text).font(compact ? .callout : .body).textSelection(.enabled).lineSpacing(compact ? 0 : 5)
    }
}
#endif
