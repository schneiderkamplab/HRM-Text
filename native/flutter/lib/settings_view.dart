import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'store.dart';

class SettingsView extends StatefulWidget {
  final ChatStore store;
  const SettingsView({super.key, required this.store});
  @override
  State<SettingsView> createState() => _SettingsViewState();
}

class _SettingsViewState extends State<SettingsView> {
  late final c = TextEditingController(text: '${s.context}'),
      r = TextEditingController(text: '${s.reply}');
  late String device = s.device;
  ChatStore get s => widget.store;
  @override
  void dispose() {
    c.dispose();
    r.dispose();
    super.dispose();
  }

  Future<void> pick(bool profile) async {
    final result = await FilePicker.pickFiles();
    final path = result.firstOrNull?.path;
    if (path == null) return;
    if (profile) {
      await s.importProfile(path);
    } else {
      await s.importModel(path);
    }
    if (mounted) {
      c.text = '${s.context}';
      r.text = '${s.reply}';
      setState(() {});
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: s,
    builder: (_, _) => AlertDialog(
      title: const Text('Model and settings'),
      content: SizedBox(
        width: 520,
        child: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                s.model?['name'] ?? 'No model loaded',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Text(
                'Mimir runs on your device using its own chat template. No account or server required.',
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: s.busy ? null : () => pick(false),
                    child: const Text('Import Mimir GGUF…'),
                  ),
                  TextButton(
                    onPressed: s.busy ? null : s.useBundled,
                    child: const Text('Use bundled model'),
                  ),
                ],
              ),
              Text('Profile: ${s.profile.name}'),
              TextButton(
                onPressed: s.busy || s.model == null ? null : () => pick(true),
                child: const Text('Import model profile…'),
              ),
              DropdownButtonFormField<String>(
                initialValue: device,
                decoration: const InputDecoration(labelText: 'Compute device'),
                items: [
                  const DropdownMenuItem(
                    value: 'auto',
                    child: Text('Automatic'),
                  ),
                  if (device != 'auto' &&
                      !s.devices.any((d) => d['id'] == device))
                    DropdownMenuItem(
                      value: device,
                      child: Text('$device (unavailable)'),
                    ),
                  for (final d in s.devices)
                    DropdownMenuItem(
                      value: d['id'] as String,
                      child: Text(
                        '${d['backend']} · ${d['name']}',
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: s.busy
                    ? null
                    : (v) {
                        if (v != null) setState(() => device = v);
                      },
              ),
              const SizedBox(height: 18),
              TextField(
                controller: c,
                enabled: !s.busy,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Context tokens'),
              ),
              TextField(
                controller: r,
                enabled: !s.busy,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Reply budget tokens',
                ),
              ),
              Text('Active: ${s.context} context · ${s.reply} reply tokens'),
              if (s.training != null)
                Text(
                  'Model trained with a maximum context of ${s.training} tokens. Longer contexts may reduce answer quality.',
                ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: s.busy
                        ? null
                        : () async {
                            final contextTokens = int.tryParse(c.text),
                                replyTokens = int.tryParse(r.text);
                            if (contextTokens == null || replyTokens == null) {
                              s.setNotice(
                                'Enter whole numbers for both limits.',
                              );
                              return;
                            }
                            await s.setLimits(
                              contextTokens,
                              replyTokens,
                              backend: device,
                            );
                          },
                    child: const Text('Apply limits'),
                  ),
                  TextButton(
                    onPressed: s.busy
                        ? null
                        : () async {
                            await s.setLimits(
                              s.context,
                              s.reply,
                              auto: true,
                              backend: device,
                            );
                            c.text = '${s.context}';
                            r.text = '${s.reply}';
                          },
                    child: const Text('Use memory-based defaults'),
                  ),
                ],
              ),
              const Text(
                'Automatic defaults use a memory estimate. Custom limits override that estimate; excessive context may fail to load or exhaust memory.',
              ),
              TextButton(
                onPressed: () => showLicensePage(
                  context: context,
                  applicationName: 'DFM Mimir',
                ),
                child: const Text('Licenses and acknowledgements'),
              ),
              const Divider(),
              SwitchListTile(
                key: const Key('mixed-lm-setting'),
                contentPadding: EdgeInsets.zero,
                title: const Text('MixedLM mode'),
                subtitle: const Text(
                  'Experimental. Reuses older context to reduce the wait before replies. '
                  'May change answer quality. Off uses exact PrefixLM.',
                ),
                value: s.mixedLM,
                onChanged: s.busy || s.model == null ? null : s.setMixedLM,
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Automatically summarize older turns'),
                value: s.compact,
                onChanged: s.busy ? null : (v) => s.setCompaction(enabled: v),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Show compaction summary in chat'),
                value: s.showSummary,
                onChanged: s.busy ? null : (v) => s.setCompaction(visible: v),
              ),
              const Text(
                'The full transcript is preserved. Summaries may omit details. Turning compaction off uses the full history again.',
              ),
              if (s.notice != null)
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: Text(
                    s.notice!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Done'),
        ),
      ],
    ),
  );
}
