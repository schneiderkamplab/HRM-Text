import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'store.dart';
import 'model_library_view.dart';

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
  late final apiPort = TextEditingController(text: '${s.apiPort}');
  ChatStore get s => widget.store;
  @override
  void dispose() {
    apiPort.dispose();
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
              TextButton.icon(
                icon: const Icon(Icons.storage),
                label: const Text('Choose or download a model…'),
                onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                  builder: (_) => ModelLibraryView(store: s),
                )),
              ),
              Wrap(
                spacing: 8,
                children: [
                  TextButton(
                    onPressed: s.busy ? null : () => pick(false),
                    child: const Text('Import Mimir GGUF…'),
                  ),
                  TextButton(
                    onPressed: s.busy
                        ? null
                        : () => s.useBundled(loadModel: !s.manualStartup),
                    child: const Text('Use bundled model'),
                  ),
                ],
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Allow online feedback'),
                subtitle: const Text(
                  'Off by default. Allows feedback uploads; each upload still requires confirmation. Chat and generation stay on this device.',
                ),
                value: s.onlineFeedback,
                onChanged: s.setOnlineFeedback,
              ),
              Text('Profile: ${s.profile.name}'),
              Text(s.engineLabel),
              if (s.desktop) ...[
                const Divider(),
                TextField(
                  controller: apiPort,
                  enabled: s.apiServer == null,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Local API port',
                  ),
                ),
                SwitchListTile(
                  title: const Text('OpenAI-compatible local API'),
                  subtitle: Text(
                    s.apiServer?.address ?? 'Off · localhost only',
                  ),
                  value: s.apiServer != null,
                  onChanged: (enabled) async {
                    final port = int.tryParse(apiPort.text);
                    if (port == null || port < 1 || port > 65535) {
                      s.setNotice('API port must be 1–65535.');
                      return;
                    }
                    await s.setApiEnabled(enabled, port: port);
                  },
                ),
                if (s.apiBusy) const Text('Serving API requests…'),
                const Divider(),
              ],
              if (s.backendFallbackReasons.isNotEmpty)
                Text(
                  'Automatic fallback: ${s.backendFallbackReasons.join('; ')}',
                ),
              TextButton(
                onPressed: s.busy || s.model == null ? null : () => pick(true),
                child: const Text('Import model profile…'),
              ),
              DropdownButtonFormField<String>(
                isExpanded: true,
                key: ValueKey(device),
                initialValue: device,
                decoration: const InputDecoration(labelText: 'Compute device'),
                items: [
                  if (!s.manualStartup)
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
                  if (!s.manualStartup)
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
              if (s.manualStartup) ...[
                TextButton(
                  onPressed: s.busy
                      ? null
                      : () async {
                          final minimum = s.profile.number('minimumContext');
                          final budget = s.profile.defaultReply(minimum);
                          await s.setLimits(minimum, budget, backend: 'cpu');
                          if (mounted) {
                            setState(() {
                              device = 'cpu';
                              c.text = '$minimum';
                              r.text = '$budget';
                            });
                          }
                        },
                  child: const Text('Use conservative CPU settings'),
                ),
                FilledButton(
                  onPressed: s.busy
                      ? null
                      : () async {
                          final contextTokens = int.tryParse(c.text),
                              replyTokens = int.tryParse(r.text);
                          if (contextTokens == null ||
                              replyTokens == null ||
                              s.profile.limitsError(
                                    contextTokens,
                                    replyTokens,
                                  ) !=
                                  null) {
                            s.setNotice(
                              'Enter valid context and reply limits before loading.',
                            );
                            return;
                          }
                          await s.setLimits(
                            contextTokens,
                            replyTokens,
                            backend: device,
                            reload: false,
                          );
                          await s.startModel();
                        },
                  child: const Text('Load model'),
                ),
                const Text(
                  'Android starts without loading a model. Vulkan is experimental. If the app or device freezes, force-stop Mimir and reopen it to choose CPU and a smaller context. Switching backends after loading requires force-stop and reopen.',
                ),
              ],
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
              Text('Temperature: ${s.temperature.toStringAsFixed(2)}'),
              Slider(
                key: const Key('temperature-setting'),
                value: s.temperature, min: 0, max: 2, divisions: 40,
                label: s.temperature.toStringAsFixed(2),
                onChanged: s.busy ? null : (v) => s.setSampling(
                  temperature: v, repetitionPenalty: s.repetitionPenalty),
              ),
              const Text('0 chooses the most likely token. Higher values add variety.'),
              Text('Repetition penalty: ${s.repetitionPenalty.toStringAsFixed(2)}'),
              Slider(
                key: const Key('repetition-penalty-setting'),
                value: s.repetitionPenalty, min: 1, max: 2, divisions: 100,
                label: s.repetitionPenalty.toStringAsFixed(2),
                onChanged: s.busy ? null : (v) => s.setSampling(
                  temperature: s.temperature, repetitionPenalty: v),
              ),
              const Text('1 disables the penalty. Higher values discourage repeating the last 64 generated tokens in this reply.'),
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
                title: const Text('Automatically compact context'),
                subtitle: const Text(
                  'Summarize older turns and shorten oversized prompts in chunks.',
                ),
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
