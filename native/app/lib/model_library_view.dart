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
              'Selected: ${store.model?['name'] ?? 'Bundled DFM Mimir v1 Q4_K_M'}',
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
            if (library.error != null) Text(library.error!),
            if (store.notice != null) Text(store.notice!),
            Card(
              child: ListTile(
                title: const Text('DFM Mimir v1 Q4_K_M'),
                subtitle: const Text(
                  'Bundled · 1.17 GB · no download needed\n'
                  'Source: danish-foundation-models/DFM-Mimir\n'
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
                'Official Mimir repositories',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Text(
                'GGUF files from danish-foundation-models repositories whose names '
                'contain both “mimir” and “gguf” (case-insensitive) are added automatically on refresh. Discovery '
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
