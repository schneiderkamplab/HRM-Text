import 'package:flutter/material.dart';

import 'search.dart';
import 'settings_widgets.dart';

class SearchSettings extends StatefulWidget {
  final WebSearchController search;
  final VoidCallback onChanged;
  const SearchSettings({
    super.key,
    required this.search,
    required this.onChanged,
  });
  @override
  State<SearchSettings> createState() => _SearchSettingsState();
}

class _SearchSettingsState extends State<SearchSettings> {
  final keyInput = TextEditingController();
  bool remember = true, saving = false, loading = true, visible = false;
  String? error;
  @override
  void initState() {
    super.initState();
    loadKey();
  }

  Future<void> loadKey() async {
    await widget.search.load();
    if (!mounted) return;
    setState(() {
      keyInput.text = widget.search.configuredKey;
      loading = false;
    });
  }

  @override
  void dispose() {
    keyInput.dispose();
    super.dispose();
  }

  Future<void> save(String value) async {
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.search.setKey(value, remember: remember);
      if (!mounted) return;
      keyInput.text = widget.search.configuredKey;
      visible = false;
    } on FormatException catch (e) {
      error = e.message;
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: widget.search,
    builder: (_, _) => Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Allow online search'),
          subtitle: const Text(
            'Off by default. Allows Mimir to search through the Mimir service and Jina AI. Only search queries are sent, but they may include details from your chat.',
          ),
          value: widget.search.enabled,
          onChanged: (v) {
            widget.search.setEnabled(v);
            widget.onChanged();
          },
        ),
        SettingsValue(
          'Key status',
          widget.search.configured
              ? 'Search key configured'
              : 'No search key configured',
        ),
        TextField(
          controller: keyInput,
          obscureText: !visible,
          obscuringCharacter: '*',
          autocorrect: false,
          enableSuggestions: false,
          enabled: !saving && !loading,
          decoration: settingsInput('Search key').copyWith(
            hintText: 'mimir_<hex>',
            suffixIcon: IconButton(
              tooltip: visible ? 'Hide search key' : 'Show search key',
              icon: Icon(visible ? Icons.visibility_off : Icons.visibility),
              onPressed: saving || loading
                  ? null
                  : () => setState(() => visible = !visible),
            ),
          ),
        ),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Remember key in secure storage'),
          value: remember,
          onChanged: saving ? null : (v) => setState(() => remember = v!),
        ),
        Wrap(
          children: [
            FilledButton.tonal(
              onPressed: saving || loading ? null : () => save(keyInput.text),
              child: const Text('Save search key'),
            ),
            TextButton(
              onPressed: saving || loading ? null : () => save(''),
              child: const Text('Forget search key'),
            ),
          ],
        ),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        if (widget.search.message != null) SettingsHelp(widget.search.message!),
      ],
    ),
  );
}
