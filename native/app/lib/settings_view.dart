import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'search_view.dart';
import 'settings_widgets.dart';
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
  int selectedTab = 0;
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
    builder: (_, _) => DefaultTabController(
      length: 4,
      child: AlertDialog(
        title: const Text('Settings'),
        content: SizedBox(
          width: 560,
          height: 600,
          child: Column(
            children: [
              TabBar(
                isScrollable: true,
                labelPadding: const EdgeInsets.symmetric(horizontal: 12),
                tabAlignment: TabAlignment.start,
                onTap: (index) => setState(() => selectedTab = index),
                tabs: const [
                  Tab(text: 'Model'),
                  Tab(text: 'Appearance'),
                  Tab(text: 'Online'),
                  Tab(text: 'Advanced'),
                ],
              ),
              const SizedBox(height: 16),
              Expanded(
                child: IndexedStack(
                  index: selectedTab,
                  children: [
                    settingsPage('model', modelSettings(context)),
                    settingsPage('appearance', appearanceSettings(context)),
                    settingsPage('online', onlineSettings(context)),
                    settingsPage('advanced', advancedSettings(context)),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Done'),
          ),
        ],
      ),
    ),
  );

  Widget settingsPage(String name, List<Widget> children) =>
      SingleChildScrollView(
        key: PageStorageKey('settings-$name'),
        primary: false,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ...children,
            if (s.notice != null)
              Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(
                  s.notice!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
          ],
        ),
      );

  List<Widget> modelSettings(BuildContext context) => [
    SettingsSection(
      title: 'Selected model',
      children: [
        SettingsValue('Model', s.model?['name'] ?? 'No model selected'),
        FilledButton.tonalIcon(
          icon: const Icon(Icons.storage),
          label: const Text('Choose or download a model…'),
          onPressed: () => Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => ModelLibraryView(store: s)),
          ),
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
        const SizedBox(height: 12),
        SettingsValue('Status', s.modelStatus),
      ],
    ),
    SettingsSection(
      title: 'Generation',
      children: [
        const SettingsHelp('Changes apply to the next reply.'),
        SettingsValue('Temperature', s.temperature.toStringAsFixed(2)),
        Slider(
          key: const Key('temperature-setting'),
          value: s.temperature,
          min: 0,
          max: 2,
          divisions: 40,
          label: s.temperature.toStringAsFixed(2),
          onChanged: s.busy
              ? null
              : (v) => s.setSampling(
                  temperature: v,
                  repetitionPenalty: s.repetitionPenalty,
                ),
        ),
        const SettingsHelp(
          '0 chooses the most likely token. Higher values add variety.',
        ),
        const Divider(height: 32),
        SettingsValue(
          'Repetition penalty',
          s.repetitionPenalty.toStringAsFixed(2),
        ),
        Slider(
          key: const Key('repetition-penalty-setting'),
          value: s.repetitionPenalty,
          min: 1,
          max: 2,
          divisions: 100,
          label: s.repetitionPenalty.toStringAsFixed(2),
          onChanged: s.busy
              ? null
              : (v) => s.setSampling(
                  temperature: s.temperature,
                  repetitionPenalty: v,
                ),
        ),
        const SettingsHelp(
          '1 disables the penalty. Higher values discourage repeating the last 64 generated tokens in this reply.',
        ),
      ],
    ),
    SettingsSection(
      title: 'Memory and compute',
      children: [
        SettingsValue(
          'Current device',
          s.ready ? s.engineLabel : 'No model loaded',
        ),
        if (s.backendFallbackReasons.isNotEmpty)
          SettingsHelp(
            'Automatic fallback: ${s.backendFallbackReasons.join('; ')}',
          ),
        DropdownButtonFormField<String>(
          isExpanded: true,
          key: ValueKey(device),
          initialValue: device,
          decoration: settingsInput('Acceleration backend'),
          items: [
            if (!s.manualStartup)
              const DropdownMenuItem(value: 'auto', child: Text('Automatic')),
            if (device != 'auto' && !s.devices.any((d) => d['id'] == device))
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
          decoration: settingsInput('Context tokens'),
        ),
        const SizedBox(height: 18),
        TextField(
          controller: r,
          enabled: !s.busy,
          keyboardType: TextInputType.number,
          decoration: settingsInput('Reply budget tokens'),
        ),
        const SizedBox(height: 16),
        SettingsValue(
          'Applied limits',
          '${s.context} context · ${s.reply} reply tokens',
        ),
        const SettingsHelp(
          'Edit the fields above, then apply. Applying on desktop reloads the model.',
        ),
        if (s.training != null)
          SettingsHelp(
            'Model trained with a maximum context of ${s.training} tokens. Longer contexts may reduce answer quality.',
          ),
        Wrap(
          spacing: 8,
          children: [
            FilledButton.tonal(
              onPressed: s.busy
                  ? null
                  : () async {
                      final contextTokens = int.tryParse(c.text),
                          replyTokens = int.tryParse(r.text);
                      if (contextTokens == null || replyTokens == null) {
                        s.setNotice('Enter whole numbers for both limits.');
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
                        s.profile.limitsError(contextTokens, replyTokens) !=
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
          const SettingsHelp(
            'Android starts without loading a model. Vulkan is experimental. If the app or device freezes, force-stop Mimir and reopen it to choose CPU and a smaller context. Switching backends after loading requires force-stop and reopen.',
          ),
        ],
        const SettingsHelp(
          'Automatic defaults use a memory estimate. Custom limits override that estimate; excessive context may fail to load or exhaust memory.',
        ),
      ],
    ),
  ];

  List<Widget> appearanceSettings(BuildContext context) => [
    SettingsSection(
      title: 'Text',
      children: [
        SettingsValue('Text size', '${(s.textScale * 100).round()}%'),
        Slider(
          key: const Key('text-size'),
          value: s.textScale,
          min: ChatStore.minimumTextScale,
          max: ChatStore.maximumTextScale,
          divisions: 25,
          label: '${(s.textScale * 100).round()}%',
          semanticFormatterCallback: (value) =>
              '${(value * 100).round()} percent',
          onChanged: s.setTextScale,
        ),
        const SettingsHelp(
          'Scales all app text in addition to your device’s text size.',
        ),
        TextButton(
          onPressed: s.textScale == 1 ? null : () => s.setTextScale(1),
          child: const Text('Reset text size'),
        ),
      ],
    ),
  ];

  List<Widget> onlineSettings(BuildContext context) => [
    SettingsSection(
      title: 'Conversation feedback',
      children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Allow online feedback'),
          subtitle: const Text(
            'Off by default. Allows feedback uploads; each upload still requires confirmation. Chat and generation stay on this device.',
          ),
          value: s.onlineFeedback,
          onChanged: s.setOnlineFeedback,
        ),
      ],
    ),
    SettingsSection(
      title: 'Web search',
      children: [SearchSettings(search: s.search, onChanged: s.save)],
    ),
  ];

  List<Widget> advancedSettings(BuildContext context) => [
    SettingsSection(
      title: 'Context compaction',
      children: [
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
          subtitle: const Text(
            'Display summaries in the transcript as they are generated.',
          ),
          value: s.showSummary,
          onChanged: s.busy ? null : (v) => s.setCompaction(visible: v),
        ),
        const SettingsHelp(
          'The full transcript is preserved. Summaries may omit details. Turning compaction off uses the full history again.',
        ),
      ],
    ),
    if (s.desktop) ...[
      SettingsSection(
        title: 'Local API',
        children: [
          const SettingsHelp(
            'Choose a port before switching the API on. Turn it off to change the port.',
          ),
          TextField(
            controller: apiPort,
            enabled: s.apiServer == null,
            keyboardType: TextInputType.number,
            decoration: settingsInput('Local API port'),
          ),
          const SizedBox(height: 12),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            title: const Text('OpenAI-compatible local API'),
            subtitle: const Text(
              'Allow applications on this computer to use Mimir.',
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
          SettingsValue(
            'Listening address',
            s.apiServer?.address ?? 'Off · localhost only',
          ),
          if (s.apiBusy) const SettingsHelp('Serving API requests…'),
        ],
      ),
    ],
    SettingsSection(
      title: 'Model profiles',
      children: [
        SettingsValue('Selected profile', s.profile.name),
        const SettingsHelp('Import a model-specific configuration file.'),
        TextButton(
          onPressed: s.busy || s.model == null ? null : () => pick(true),
          child: const Text('Import model profile…'),
        ),
      ],
    ),
    SettingsSection(
      title: 'Experimental inference',
      children: [
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
      ],
    ),
    SettingsSection(
      title: 'About',
      children: [
        TextButton(
          onPressed: () =>
              showLicensePage(context: context, applicationName: 'DFM Mimir'),
          child: const Text('Licenses and acknowledgements'),
        ),
      ],
    ),
  ];
}
