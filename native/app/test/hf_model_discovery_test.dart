import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/hf_model_discovery.dart';
import 'package:dfm_mimir/model_library.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('case-insensitive official repo matching, nested GGUFs, pagination and pinning', () async {
    final profile = jsonDecode(
      await rootBundle.loadString('assets/profile.json'),
    ) as Map<String, dynamic>;
    final requests = <Uri>[];
    final discovery = HfModelDiscovery((uri) async {
      requests.add(uri);
      if (uri.path == '/api/models') {
        if (uri.queryParameters['cursor'] == 'next') {
          return DiscoveryPage([
            {'id': 'danish-foundation-models/DFM-MiMiR-GgUf-v2'},
          ]);
        }
        expect(uri.queryParameters['author'], 'danish-foundation-models');
        return DiscoveryPage([
          {'id': 'someone/DFM-Mimir-GGUF'},
          {'id': 'danish-foundation-models/not-a-match'},
          {'id': 'danish-foundation-models/DFM-Mimir'},
          {'id': 'danish-foundation-models/DFM-GGUF'},
        ], Uri.https('huggingface.co', '/api/models', {'cursor': 'next'}));
      }
      if (!uri.path.contains('/tree/')) return DiscoveryPage({'sha': 'a' * 40});
      expect(uri.path, endsWith('/tree/${'a' * 40}'));
      if (uri.queryParameters['cursor'] == 'next') {
        return DiscoveryPage([
          {
            'type': 'file',
            'path': 'nested/model.GGUF',
            'size': 42,
            'lfs': {'oid': 'b' * 64},
          },
        ]);
      }
      return DiscoveryPage([
        {'type': 'file', 'path': 'model.safetensors'},
        {'type': 'directory', 'path': 'folder.gguf'},
      ], uri.replace(queryParameters: {'cursor': 'next'}));
    });
    await discovery.discover(profile);
    expect(requests.length, 5);
    expect(discovery.repositories, ['danish-foundation-models/DFM-MiMiR-GgUf-v2']);
    final artifact = ModelArtifact(discovery.artifacts.single);
    expect(artifact.id, 'b' * 64);
    expect(artifact.bytes, 42);
    expect(
      artifact.url.path,
      contains('/resolve/${'a' * 40}/nested/model.GGUF'),
    );
    expect(artifact.data['source'], 'hf-discovery');
  });
  test(
    'split files and missing integrity metadata are listed with reasons',
    () async {
      final discovery = HfModelDiscovery((uri) async {
        if (uri.path == '/api/models') {
          return DiscoveryPage([
            {'id': 'danish-foundation-models/mimir-gguf'},
          ]);
        }
        if (!uri.path.contains('/tree/')) {
          return DiscoveryPage({'sha': 'a' * 40});
        }
        return DiscoveryPage([
          {
            'type': 'file',
            'path': 'model-00001-of-00002.gguf',
            'size': 42,
            'lfs': {'oid': 'b' * 64},
          },
          {'type': 'file', 'path': 'no-hash.gguf', 'size': 42},
        ]);
      });
      await discovery.discover({});
      expect(discovery.artifacts, isEmpty);
      expect(discovery.unavailable.length, 2);
      expect(discovery.unavailable.first['reason'], contains('Split GGUF'));
      expect(discovery.unavailable.last['reason'], contains('SHA-256'));
    },
  );
  test('pagination cannot escape HF or loop', () async {
    for (final next in [
      Uri.https('other.example', '/api/models'),
      Uri.https('huggingface.co', '/api/models', {
        'author': HfModelDiscovery.owner,
        'limit': '100',
      }),
    ]) {
      final discovery = HfModelDiscovery((_) async => DiscoveryPage([], next));
      await expectLater(discovery.discover({}), throwsFormatException);
    }
  });
}
