import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'feedback.dart';

class FeedbackDialog extends StatefulWidget {
  final FeedbackSnapshot snapshot;
  final String rating, pseudonym;
  final Future<String> Function(String) submit;
  final Future<void> Function(String) savePseudonym;
  const FeedbackDialog({
    super.key,
    required this.snapshot,
    required this.rating,
    required this.pseudonym,
    required this.submit,
    required this.savePseudonym,
  });
  @override
  State<FeedbackDialog> createState() => _FeedbackDialogState();
}

class _FeedbackDialogState extends State<FeedbackDialog> {
  late final name = TextEditingController(text: widget.pseudonym);
  final comment = TextEditingController();
  final draft = FeedbackDraft();
  bool publication = true, busy = false;
  String? error, receipt;
  @override
  void dispose() {
    name.dispose();
    comment.dispose();
    super.dispose();
  }

  String get body => draft.encode(
    widget.snapshot,
    rating: widget.rating,
    pseudonym: name.text,
    comment: comment.text,
    publication: publication,
  );

  Future<void> send() async {
    if (name.text.trim().isEmpty) {
      setState(() => error = 'Choose an attribution name.');
      return;
    }
    final payload = body;
    if (utf8.encode(payload).length > feedbackMaxBytes) {
      setState(() => error = 'This chat exceeds the 1 MiB feedback limit.');
      return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final id = await widget.submit(payload);
      // A local preference failure must not turn a successful upload into a retry.
      try {
        await widget.savePseudonym(name.text);
      } catch (_) {
        /* Receipt still valid. */
      }
      if (mounted) setState(() => receipt = id);
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is FeedbackFailure
              ? e.message
              : 'Delivery could not be confirmed. Please retry.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: AlertDialog(
      title: Text(
        receipt == null
            ? 'Share ${widget.rating == 'up' ? 'positive' : 'negative'} feedback'
            : 'Thank you for your feedback',
      ),
      content: SizedBox(
        width: 620,
        child: SingleChildScrollView(
          child: receipt != null
              ? Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Your feedback was received. Keep this receipt if you need to contact us about it.',
                    ),
                    const SizedBox(height: 12),
                    SelectableText(receipt!),
                    const SizedBox(height: 12),
                    const SelectableText(feedbackContact),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text(
                      'Send this entire chat, including any compaction summary, your rating, comment and the metadata shown below to the Mimir team to improve future versions of Mimir and other DFM models.',
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Check the preview for personal or confidential information before sending. Nothing is uploaded until you press Confirm and send.',
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: name,
                      enabled: !busy,
                      maxLength: 80,
                      decoration: InputDecoration(
                        labelText: 'Attribution pseudonym',
                        helperText:
                            'Randomly generated on this device; editable.',
                        suffixIcon: IconButton(
                          tooltip: 'Generate a new pseudonym',
                          onPressed: busy
                              ? null
                              : () => setState(
                                  () => name.text = FeedbackIdentity.generate(),
                                ),
                          icon: const Icon(Icons.refresh),
                        ),
                      ),
                      onChanged: (_) => setState(() {}),
                    ),
                    TextField(
                      controller: comment,
                      enabled: !busy,
                      maxLength: 4000,
                      minLines: 2,
                      maxLines: 5,
                      decoration: const InputDecoration(
                        labelText: 'Comment (optional)',
                      ),
                      onChanged: (_) => setState(() {}),
                    ),
                    CheckboxListTile(
                      contentPadding: EdgeInsets.zero,
                      value: publication,
                      onChanged: busy
                          ? null
                          : (v) => setState(() => publication = v!),
                      title: const Text(
                        'Allow this feedback and chat to be published under CC BY 4.0',
                      ),
                      subtitle: const Text(
                        'If published after review, attribution will use the name above. CC BY permits reuse, including commercial reuse, with attribution. Uncheck to share only with the Mimir team.',
                      ),
                    ),
                    const SelectableText(
                      'License: https://creativecommons.org/licenses/by/4.0/',
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Hosted by Cloudflare. Database storage and execution are in the EU; request processing may occur elsewhere. The team retains submissions for model improvement and can review or delete them. For questions or deletion requests, contact:',
                    ),
                    const SelectableText(feedbackContact),
                    ExpansionTile(
                      title: const Text('Preview exact data to be shared'),
                      children: [
                        Align(
                          alignment: Alignment.centerLeft,
                          child: SelectableText(
                            body,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (error != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: Text(
                          error!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                  ],
                ),
        ),
      ),
      actions: receipt != null
          ? [
              TextButton(
                onPressed: () =>
                    Clipboard.setData(ClipboardData(text: receipt!)),
                child: const Text('Copy receipt'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context),
                child: const Text('Done'),
              ),
            ]
          : [
              TextButton(
                onPressed: busy ? null : () => Navigator.pop(context),
                child: const Text('Cancel'),
              ),
              TextButton(
                onPressed: busy
                    ? null
                    : () async {
                        await Clipboard.setData(ClipboardData(text: body));
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Feedback JSON copied. Nothing was uploaded.',
                              ),
                            ),
                          );
                        }
                      },
                child: const Text('Copy JSON'),
              ),
              FilledButton(
                onPressed: busy ? null : send,
                child: busy
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Confirm and send'),
              ),
            ],
    ),
  );
}
