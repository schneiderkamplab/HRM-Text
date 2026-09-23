import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';

import 'feedback.dart';
import 'feedback_dialog.dart';

import 'store.dart';
import 'chat_widgets.dart';
import 'markdown_text.dart';
import 'settings_view.dart';

class ChatView extends StatefulWidget {
  final ChatStore store;
  const ChatView({super.key, required this.store});
  @override
  State<ChatView> createState() => _ChatViewState();
}

class _ChatViewState extends State<ChatView> {
  final input = TextEditingController(),
      scroll = ScrollController(),
      focus = FocusNode();
  final summaryKey = GlobalKey();
  String previousStream = '', previousSummary = '';
  String? previousPending;
  ChatStore get s => widget.store;
  bool get mobile =>
      Theme.of(context).platform == TargetPlatform.iOS ||
      Theme.of(context).platform == TargetPlatform.android;
  @override
  void initState() {
    super.initState();
    s.addListener(changed);
  }

  @override
  void dispose() {
    s.removeListener(changed);
    input.dispose();
    scroll.dispose();
    focus.dispose();
    super.dispose();
  }

  void changed() {
    if (input.text != s.draft) {
      input.value = TextEditingValue(
        text: s.draft,
        selection: TextSelection.collapsed(offset: s.draft.length),
      );
    }
    final summary = s.visibleSummary?['summary'] as String? ?? '';
    final summaryChanged = summary != previousSummary && s.preview != null;
    final bottomChanged =
        s.streaming != previousStream || s.pending != previousPending;
    previousSummary = summary;
    previousStream = s.streaming;
    previousPending = s.pending;
    if (mounted) setState(() {});
    if (summaryChanged || bottomChanged) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!mounted) return;
        if (summaryChanged && summaryKey.currentContext != null) {
          Scrollable.ensureVisible(summaryKey.currentContext!, alignment: 1);
        } else if (scroll.hasClients) {
          scroll.jumpTo(scroll.position.maxScrollExtent);
        }
      });
    }
  }

  Future<void> send() async {
    if (s.canSend) {
      focus.unfocus();
      await s.send();
      if (!mounted) return;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !s.busy && ModalRoute.of(context)?.isCurrent == true) {
          focus.requestFocus();
        }
      });
      // Ensure the callback runs even if generation finished between frames.
      WidgetsBinding.instance.ensureVisualUpdate();
    }
  }

  Widget sidebar(bool narrow) => SafeArea(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              const MimirMark(size: 38),
              const SizedBox(width: 10),
              const Expanded(
                child: Text(
                  'DFM Mimir',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: FilledButton.tonalIcon(
            onPressed: !s.canCreateChat
                ? null
                : () {
                    s.newChat();
                    if (narrow) Navigator.pop(context);
                  },
            icon: const Icon(Icons.edit_square),
            label: const Text('New chat'),
          ),
        ),
        const Padding(
          padding: EdgeInsets.all(20),
          child: Text('YOUR CONVERSATIONS', style: TextStyle(fontSize: 11)),
        ),
        Expanded(
          child: ListView(
            children: s.chats
                .map(
                  (c) => ListTile(
                    selected: c.id == s.selected,
                    title: Text(
                      c.title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      MaterialLocalizations.of(context)
                          .formatMediumDate(c.updated),
                    ),
                    enabled: !s.busy,
                    onTap: () {
                      s.select(c.id);
                      if (narrow) Navigator.pop(context);
                    },
                  ),
                )
                .toList(),
          ),
        ),
        const Padding(
          padding: EdgeInsets.all(20),
          child: Text(
            '🔒 Private. Local. Yours.',
            style: TextStyle(fontSize: 12),
          ),
        ),
      ],
    ),
  );
  Widget summary() {
    final m = s.visibleSummary!;
    return Container(
      key: summaryKey,
      margin: const EdgeInsets.only(bottom: 26),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.summarize_outlined, size: 18),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  s.compacting
                      ? 'DFM Mimir is compacting…'
                      : 'Conversation summary',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
              if (s.compacting)
                const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: 8),
          MarkdownText(m['summary'] as String),
          const SizedBox(height: 8),
          Text(
            m['prompt'] == true
                ? 'Shortening the current prompt. Original text is preserved; summaries may omit details.'
                : 'Summarizes ${(m['covered'] as int) ~/ 2} earlier turns. Full history is preserved; summaries may omit details.',
            style: const TextStyle(fontSize: 11),
          ),
        ],
      ),
    );
  }

  Future<void> feedback(String rating) async {
    final conversation = s.active;
    final directory = s.directory;
    if (conversation == null || directory == null || s.busy) {
      return;
    }
    if (!s.onlineFeedback) {
      final allowed = await showDialog<bool>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('Allow online feedback?'),
          content: const Text(
            'DFM Mimir can connect to the Mimir feedback service when you confirm a submission. This is optional. Declining keeps feedback off and you can continue chatting offline.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Not now'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Allow feedback'),
            ),
          ],
        ),
      );
      if (allowed != true || !mounted) return;
      s.setOnlineFeedback(true);
    }
    try {
      // Capture the conversation before opening the submission dialog.
      final version = await PackageInfo.fromPlatform();
      if (!mounted || s.busy || s.active != conversation) return;
      final snapshot = FeedbackSnapshot(
        conversation: conversation,
        appVersion: '${version.version}+${version.buildNumber}',
        contextTokens: s.context,
        replyTokens: s.reply,
        mixedLM: s.mixedLM,
      );
      final identity = FeedbackIdentity(directory);
      final pseudonym = await identity.load();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        barrierDismissible: false,
        builder: (_) => FeedbackDialog(
          snapshot: snapshot,
          rating: rating,
          pseudonym: pseudonym,
          savePseudonym: identity.save,
          submit: FeedbackClient(Uri.parse(feedbackEndpoint)).submit,
        ),
      );
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Could not open feedback. Please try again.'),
          ),
        );
      }
    }
  }

  Widget transcript() {
    final children = <Widget>[];
    if (s.summaryPosition == 0) children.add(summary());
    for (var i = 0; i < s.messages.length; i++) {
      final m = s.messages[i];
      children.add(ChatMessage(role: m['role'], content: m['content']));
      if (s.showSummary && m['compactedContent'] != null) {
        children.add(
          ExpansionTile(
            title: const Text('Shortened prompt used for generation'),
            subtitle: const Text(
              'Original text preserved above; details may be omitted.',
            ),
            children: [
              Padding(
                padding: const EdgeInsets.all(14),
                child: MarkdownText(m['compactedContent'] as String),
              ),
            ],
          ),
        );
      }
      if (s.summaryPosition == i + 1) children.add(summary());
    }
    if (s.messages.isNotEmpty && feedbackEndpoint.isNotEmpty) {
      children.add(
        Row(
          children: [
            const Expanded(child: Text('Give feedback on this chat')),
            IconButton(
              tooltip: 'Positive feedback',
              onPressed: s.busy ? null : () => feedback('up'),
              icon: const Icon(Icons.thumb_up_outlined),
            ),
            IconButton(
              tooltip: 'Negative feedback',
              onPressed: s.busy ? null : () => feedback('down'),
              icon: const Icon(Icons.thumb_down_outlined),
            ),
          ],
        ),
      );
    }
    if (s.pending != null) {
      children.add(ChatMessage(role: 'user', content: s.pending!));
      children.add(
        s.streaming.isEmpty
            ? Row(
                children: [
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(s.activity)),
                ],
              )
            : ChatMessage(role: 'assistant', content: s.streaming),
      );
    }
    return SingleChildScrollView(
      controller: scroll,
      keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: children,
          ),
        ),
      ),
    );
  }

  Widget composer() => SafeArea(
    top: false,
    child: Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 20, 12),
      child: Column(
        children: [
          if (s.manualStartup && s.initialized && !s.ready && !s.busy)
            FilledButton.icon(
              onPressed: () => showDialog(
                context: context,
                builder: (_) => SettingsView(store: s),
              ),
              icon: const Icon(Icons.tune),
              label: const Text('Choose settings and load model'),
            ),
          if (mobile && MediaQuery.viewInsetsOf(context).bottom > 0)
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () => focus.unfocus(),
                icon: const Icon(Icons.keyboard_hide),
                label: const Text('Done'),
              ),
            ),
          if (!s.modelMatches)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Text(
                'This chat belongs to a different model. Load that model or start a new chat.',
              ),
            ),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Expanded(
                child: Focus(
                  onKeyEvent: (_, event) {
                    if (mobile ||
                        event is! KeyDownEvent ||
                        event.logicalKey != LogicalKeyboardKey.enter ||
                        HardwareKeyboard.instance.isShiftPressed ||
                        HardwareKeyboard.instance.isAltPressed ||
                        HardwareKeyboard.instance.isControlPressed ||
                        !input.value.composing.isCollapsed) {
                      return KeyEventResult.ignored;
                    }
                    send();
                    return KeyEventResult.handled;
                  },
                  child: TextField(
                    key: const Key('composer'),
                    controller: input,
                    focusNode: focus,
                    onChanged: s.updateDraft,
                    enabled: !s.generating,
                    minLines: 1,
                    maxLines: 5,
                    textInputAction: TextInputAction.newline,
                    decoration: const InputDecoration(
                      hintText: 'Message DFM Mimir…',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.all(Radius.circular(18)),
                      ),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              IconButton.filled(
                onPressed: s.generating
                    ? s.stop
                    : s.canSend
                    ? send
                    : null,
                tooltip: s.generating ? 'Stop reply' : 'Send message',
                icon: Icon(s.generating ? Icons.stop : Icons.arrow_upward),
              ),
            ],
          ),
          const SizedBox(height: 8),
          const Text(
            'DFM Mimir can make mistakes. Check important details.',
            style: TextStyle(fontSize: 11),
          ),
        ],
      ),
    ),
  );
  Future<void> delete() async {
    if (await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
            title: const Text('Delete this conversation?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('Delete'),
              ),
            ],
          ),
        ) ==
        true) {
      s.deleteActive();
    }
  }

  Future<void> share() async {
    final text = s.messages
        .map(
          (m) =>
              '${m['role'] == 'user' ? 'You' : 'DFM Mimir'}\n${m['content']}',
        )
        .join('\n\n');
    if (mobile || Theme.of(context).platform == TargetPlatform.macOS) {
      final box = context.findRenderObject() as RenderBox;
      await SharePlus.instance.share(
        ShareParams(
          text: text,
          sharePositionOrigin: box.localToGlobal(Offset.zero) & box.size,
        ),
      );
    } else {
      await Clipboard.setData(ClipboardData(text: text));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Conversation copied to clipboard')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final narrow = constraints.maxWidth < 800;
      return Scaffold(
        appBar: AppBar(
          title: Text(
            s.active?.title ?? 'DFM Mimir',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          actions: [
            IconButton(
              onPressed: s.canCreateChat ? s.newChat : null,
              tooltip: 'New chat',
              icon: const Icon(Icons.edit_square),
            ),
            IconButton(
              onPressed: s.initialized
                  ? () => showDialog(
                      context: context,
                      builder: (_) => SettingsView(store: s),
                    )
                  : null,
              tooltip: 'Model and settings',
              icon: const Icon(Icons.tune),
            ),
            if (s.active != null)
              PopupMenuButton<String>(
                onSelected: (v) {
                  if (v == 'delete') {
                    delete();
                  } else {
                    share();
                  }
                },
                itemBuilder: (_) => [
                  if (s.messages.isNotEmpty)
                    const PopupMenuItem(
                      value: 'share',
                      child: Text('Share conversation'),
                    ),
                  PopupMenuItem(
                    value: 'delete',
                    enabled: !s.busy,
                    child: const Text('Delete conversation'),
                  ),
                ],
              ),
          ],
        ),
        drawer: narrow ? Drawer(child: sidebar(true)) : null,
        body: Row(
          children: [
            if (!narrow) SizedBox(width: 260, child: sidebar(false)),
            if (!narrow) const VerticalDivider(width: 1),
            Expanded(
              child: Column(
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 10,
                    ),
                    child: Row(
                      children: [
                        Icon(
                          Icons.circle,
                          color: s.ready ? Colors.green : Colors.orange,
                          size: 8,
                        ),
                        const SizedBox(width: 7),
                        Expanded(
                          child: Text(
                            s.generating
                                ? s.activity
                                : s.loading
                                ? 'Loading DFM Mimir…'
                                : s.engineLabel,
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                        if (s.ready && s.modelMatches)
                          Text(
                            'Context ${s.used ?? '—'}/${s.context}',
                            style: const TextStyle(fontSize: 11),
                          ),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: s.messages.isEmpty && s.pending == null
                        ? ChatWelcome(enabled: !s.busy, onPrompt: s.updateDraft)
                        : transcript(),
                  ),
                  if (s.notice != null)
                    MaterialBanner(
                      content: Text(
                        s.notice!,
                        style: const TextStyle(fontSize: 12),
                      ),
                      actions: [
                        TextButton(
                          onPressed: () {
                            s.setNotice(null);
                          },
                          child: const Text('Dismiss'),
                        ),
                      ],
                    ),
                  composer(),
                ],
              ),
            ),
          ],
        ),
      );
    },
  );
}
