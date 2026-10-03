import 'dart:io';

import 'package:flutter/material.dart';

import 'engine.dart';
import 'model_library.dart';
import 'store.dart';

class ModelLibraryView extends StatelessWidget {
  final ChatStore store;
  const ModelLibraryView({super.key, required this.store});

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: store,
    builder: (context, _) {
      final library = store.library;
      final installed = {for (final m in library.installed) m['id']: m};
      return Scaffold(
        appBar: AppBar(title: const Text('Models')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text(
              'Selected: ${store.model?['name'] ?? 'Bundled DFM Mimir v1.5 Q4_K_M'}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const Text(
              'Weights run locally. Download size is not total memory use. '
              'Larger models also need more RAM for context and generation.',
            ),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Allow model downloads and discovery'),
              subtitle: const Text(
                'Optional. Contacts Hugging Face and the DFM Mimir '
                'catalog on GitHub when you refresh or download. No chats are sent.',
              ),
              value: library.online,
              onChanged: library.setOnline,
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                icon: const Icon(Icons.refresh),
                label: Text(
                  library.refreshing ? 'Checking…' : 'Check for newer models',
                ),
                onPressed:
                    !library.online ||
                        library.refreshing ||
                        library.downloading != null
                    ? null
                    : library.refresh,
              ),
            ),
            ListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Additional Hugging Face repositories'),
              subtitle: const Text(
                'Add an owner/repository ID to discover its GGUF files. '
                'Third-party models are unverified and may not be compatible. '
                'Adding an ID does not enable networking.',
              ),
              trailing: IconButton(
                tooltip: 'Add HF repository',
                icon: const Icon(Icons.add),
                onPressed: library.refreshing || library.downloading != null
                    ? null
                    : () => showDialog<void>(
                        context: context,
                        builder: (_) => _RepositoryDialog(library: library),
                      ),
              ),
            ),
            for (final repo in library.userRepositories)
              ListTile(
                title: Text(repo),
                trailing: IconButton(
                  tooltip: 'Remove repository',
                  icon: const Icon(Icons.remove_circle_outline),
                  onPressed: library.refreshing || library.downloading != null
                      ? null
                      : () => library.setUserRepositories(
                          library.userRepositories.where((id) => id != repo),
                        ),
                ),
              ),
            if (library.error != null) Text(library.error!),
            if (store.notice != null) Text(store.notice!),
            Card(
              child: ListTile(
                title: const Text('DFM Mimir v1.5 Q4_K_M'),
                subtitle: const Text(
                  'Bundled · 1.17 GB · no download needed\n'
                  'Source: danish-foundation-models/DFM-Mimir-v1.5-GGUF\n'
                  'Our tested GGUF conversion · trained context 4096',
                ),
                trailing: TextButton(
                  onPressed: store.busy || store.model?['bundled'] == true
                      ? null
                      : () => store.useBundled(loadModel: !store.manualStartup),
                  child: Text(
                    store.model?['bundled'] == true ? 'Selected' : 'Select',
                  ),
                ),
              ),
            ),
            for (final artifact in library.catalog)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        artifact.name,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        '${artifact.data['repo']} · ${modelSize(artifact.bytes)}',
                      ),
                      Text(artifact.data['qualification'] ?? 'Compatible GGUF'),
                      if (installed[artifact.id] != null)
                        _installed(context, installed[artifact.id]!)
                      else if (library.downloading == artifact.id) ...[
                        LinearProgressIndicator(
                          value: library.received / artifact.bytes,
                        ),
                        Text(
                          '${modelSize(library.received)} / ${modelSize(artifact.bytes)}',
                        ),
                        TextButton(
                          onPressed: library.cancel,
                          child: const Text('Cancel download'),
                        ),
                      ] else
                        Row(
                          children: [
                            const Expanded(child: Text('Not downloaded')),
                            TextButton(
                              onPressed:
                                  !library.online ||
                                      library.downloading != null ||
                                      library.refreshing
                                  ? null
                                  : () => library.download(artifact),
                              child: const Text('Download'),
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
            for (final entry in library.installed.where(
              (m) =>
                  m['bundled'] != true &&
                  !library.catalog.any((a) => a.id == m['id']),
            ))
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [Text(entry['name']), _installed(context, entry)],
                  ),
                ),
              ),
            if (library.discovered.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                'Discovered repositories',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Text(
                'GGUF files from danish-foundation-models repositories whose names '
                'contain both “mimir” and “gguf” (case-insensitive), plus your additional '
                'repositories, are checked on refresh. Discovery '
                'does not guarantee engine compatibility.',
              ),
              for (final file in library.unavailable)
                ListTile(
                  title: Text('${file['repo']} / ${file['file']}'),
                  subtitle: Text(
                    '${file['bytes'] is int ? modelSize(file['bytes']) : 'Size unknown'} · ${file['reason']}',
                  ),
                ),
              for (final repo in library.discovered)
                ListTile(title: SelectableText(repo)),
            ],
          ],
        ),
      );
    },
  );

  Widget _installed(BuildContext context, Json entry) => FutureBuilder<bool>(
    future: File(entry['path']).exists(),
    builder: (context, snapshot) {
      final exists = snapshot.data == true;
      final selected = store.model?['id'] == entry['id'];
      return Wrap(
        spacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text(
            snapshot.data == null
                ? 'Checking file…'
                : exists
                ? '${entry['repo'] == null ? 'Imported' : 'Downloaded'}${entry['bytes'] == null ? '' : ' · ${modelSize(entry['bytes'])}'}'
                : 'File missing — remove and download again',
          ),
          TextButton(
            onPressed: store.busy || selected || !exists
                ? null
                : () => store.selectModel(entry),
            child: Text(selected ? 'Selected' : 'Select'),
          ),
          TextButton(
            onPressed: store.busy || selected
                ? null
                : () => store.deleteModel(entry),
            child: const Text('Remove'),
          ),
        ],
      );
    },
  );
}

class _RepositoryDialog extends StatefulWidget {
  final ModelLibrary library;
  const _RepositoryDialog({required this.library});

  @override
  State<_RepositoryDialog> createState() => _RepositoryDialogState();
}

class _RepositoryDialogState extends State<_RepositoryDialog> {
  final controller = TextEditingController();
  String? error;

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  void add() {
    try {
      widget.library.setUserRepositories([
        ...widget.library.userRepositories,
        controller.text,
      ]);
      Navigator.of(context).pop();
    } catch (e) {
      setState(() => error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Add Hugging Face repository'),
    content: TextField(
      controller: controller,
      autofocus: true,
      autocorrect: false,
      decoration: InputDecoration(
        labelText: 'owner/repository',
        hintText: 'noctrex/DFM-Mimir',
        errorText: error,
        helperText: 'Then use “Check for newer models” to find GGUF files.',
        helperMaxLines: 2,
      ),
      onSubmitted: (_) => add(),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.of(context).pop(),
        child: const Text('Cancel'),
      ),
      TextButton(onPressed: add, child: const Text('Add')),
    ],
  );
}
