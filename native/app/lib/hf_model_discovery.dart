import 'engine.dart';

/// Shared policy for curated, cached and discovered downloadable models.
bool isOfficialMimirGgufRepository(Object? repository) {
  if (repository is! String) return false;
  final parts = repository.toLowerCase().split('/');
  return parts.length == 2 &&
      parts.first == HfModelDiscovery.owner &&
      parts.last.contains('mimir') &&
      parts.last.contains('gguf');
}

bool isHfRepositoryId(String repository) =>
    RegExp(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*/[a-zA-Z0-9][a-zA-Z0-9_.-]*$')
        .hasMatch(repository) &&
    !repository.contains('..');

class DiscoveryPage {
  final Object? data;
  final Uri? next;
  DiscoveryPage(this.data, [this.next]);
}

class HfModelDiscovery {
  static const owner = 'danish-foundation-models';
  final Future<DiscoveryPage> Function(Uri) fetch;
  HfModelDiscovery(this.fetch);
  final repositories = <String>[];
  final artifacts = <Json>[];
  final unavailable = <Json>[];

  Stream<Json> _pages(Uri uri) async* {
    final seen = <Uri>{};
    Uri? next = uri;
    while (next != null) {
      if (next.scheme != 'https' ||
          next.host != 'huggingface.co' ||
          !next.path.startsWith('/api/models') ||
          !seen.add(next)) {
        throw const FormatException('Invalid HF pagination link');
      }
      final page = await fetch(next);
      for (final entry in page.data as List) {
        yield Json.from(entry);
      }
      next = page.next;
    }
  }

  Future<void> discover(Json fallbackProfile) async {
    await for (final model in _pages(
      Uri.https('huggingface.co', '/api/models', {
        'author': owner,
        'limit': '100',
      }),
    )) {
      final repo = model['id'] as String;
      if (!isOfficialMimirGgufRepository(repo)) {
        continue;
      }
      await discoverRepository(repo, fallbackProfile);
    }
  }

  Future<void> discoverRepository(
    String repo,
    Json fallbackProfile, {
    bool userSupplied = false,
  }) async {
    if (!isHfRepositoryId(repo)) {
      throw const FormatException('Use a Hugging Face ID: owner/repository');
    }
    final parts = repo.split('/');
    repositories.add(repo);
    final info =
        (await fetch(Uri.https('huggingface.co', '/api/models/$repo'))).data
            as Map;
    final revision = info['sha'] as String;
    if (!RegExp(r'^[a-f0-9]{40}$').hasMatch(revision)) {
      throw const FormatException('HF did not provide an immutable revision');
    }
    await for (final file in _pages(
      Uri.https('huggingface.co', '/api/models/$repo/tree/$revision', {
        'recursive': 'true',
        'limit': '1000',
      }),
    )) {
      final name = file['path'] as String;
      if (file['type'] != 'file' || !name.toLowerCase().endsWith('.gguf')) {
        continue;
      }
      final hash = (file['lfs'] as Map?)?['oid'];
      final bytes = file['size'];
      String? reason;
      if (hash is! String ||
          !RegExp(r'^[a-f0-9]{64}$').hasMatch(hash) ||
          bytes is! int ||
          bytes <= 0) {
        reason =
            'HF has not supplied a SHA-256 and size for verified downloading.';
      } else if (RegExp(
        r'-\d{5}-of-\d{5}\.gguf$',
        caseSensitive: false,
      ).hasMatch(name)) {
        reason = 'Split GGUF: downloading and loading a shard set is not yet supported.';
      }
      if (reason != null) {
        unavailable.add({
          'repo': repo,
          'file': name,
          'bytes': bytes,
          'reason': reason,
        });
        continue;
      }
      artifacts.add({
        'id': hash,
        'name': '${parts.last} · $name',
        'repo': repo,
        'revision': revision,
        'file': name,
        'bytes': bytes,
        'source': 'hf-discovery',
        'profile': {
          ...fallbackProfile,
          'name': 'Unverified Mimir discovery profile',
        },
        'qualification':
            '${userSupplied ? 'User-specified repository' : 'Official DFM repository · automatically discovered'}. '
            'Not yet app-qualified; uses conservative Mimir v1 memory/context defaults. '
            'New architectures may need an app update. Import a model-specific profile if needed.',
      });
    }
  }
}
