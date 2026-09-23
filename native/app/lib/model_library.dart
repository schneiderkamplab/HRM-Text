import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;

import 'engine.dart';
import 'models.dart';
import 'hf_model_discovery.dart';

/// A reviewed catalog pins artifacts and profiles. HF discovery never grants
/// compatibility merely because a repository contains "Mimir" in its name.
class ModelArtifact {
  final Json data;
  ModelArtifact(this.data) {
    if (data['name'] is! String ||
        (data['name'] as String).trim().isEmpty ||
        (data['qualification'] != null && data['qualification'] is! String) ||
        !RegExp(r'^[a-f0-9]{64}$').hasMatch(id) ||
        !RegExp(r'^[a-f0-9]{40}$').hasMatch(data['revision'] as String) ||
        !RegExp(r'^[\w.-]+/[\w.-]+$').hasMatch(data['repo'] as String) ||
        !(data['file'] as String).toLowerCase().endsWith('.gguf') ||
        (data['file'] as String)
            .split('/')
            .any((s) => s == '..' || s.isEmpty) ||
        bytes <= 0 ||
        bytes > 100 * 1000 * 1000 * 1000) {
      throw const FormatException('Invalid model artifact');
    }
    ModelProfile(Json.from(data['profile']));
  }
  String get id => data['id'];
  int get bytes => data['bytes'];
  String get name => data['name'];
  Uri get url => Uri.https(
    'huggingface.co',
    '${data['repo']}/resolve/${data['revision']}/${data['file']}',
  );
}

String modelSize(int bytes) => bytes >= 1000000000
    ? '${(bytes / 1000000000).toStringAsFixed(2)} GB'
    : '${(bytes / 1000000).toStringAsFixed(1)} MB';

class ModelLibrary extends ChangeNotifier {
  static final catalogUrl = Uri.parse(
    'https://raw.githubusercontent.com/schneiderkamplab/HRM-Text/main/native/app/assets/models.json',
  );
  Directory? directory;
  final HttpClient Function() clientFactory;
  ModelLibrary({HttpClient Function()? clientFactory})
    : clientFactory = clientFactory ?? HttpClient.new;
  VoidCallback? onChanged;
  bool online = false, refreshing = false;
  List<ModelArtifact> catalog = [];
  List<Json> installed = [];
  List<String> discovered = [];
  List<String> userRepositories = [];

  bool allowsRepository(Object? repo) =>
      isOfficialMimirGgufRepository(repo) ||
      (repo is String &&
          userRepositories.any((id) => id.toLowerCase() == repo.toLowerCase()));

  void setUserRepositories(Iterable<String> repositories) {
    if (_work != null) {
      throw StateError('Wait for the current model operation to finish');
    }
    final normalized = <String, String>{};
    for (final value in repositories) {
      final id = value.trim();
      if (!isHfRepositoryId(id)) {
        throw const FormatException('Use a Hugging Face ID: owner/repository');
      }
      normalized.putIfAbsent(id.toLowerCase(), () => id);
    }
    userRepositories = normalized.values.toList();
    catalog.removeWhere((a) => !allowsRepository(a.data['repo']));
    discovered.removeWhere((repo) => !allowsRepository(repo));
    unavailable.removeWhere((entry) => !allowsRepository(entry['repo']));
    onChanged?.call();
    notifyListeners();
  }

  List<Json> unavailable = [];
  String? downloading, error;
  int received = 0;
  HttpClient? _client;
  bool _cancelled = false;
  Future<void>? _work;

  void readCatalog(String text) {
    final json = jsonDecode(text) as Json;
    if (json['version'] != 1) {
      throw const FormatException('Unknown catalog version');
    }
    final entries = (json['models'] as List)
        .where((e) => allowsRepository(e['repo']))
        .map((e) => ModelArtifact(Json.from(e)))
        .toList();
    if (entries.map((e) => e.id).toSet().length != entries.length) {
      throw const FormatException('Duplicate catalog artifact');
    }
    catalog = entries;
  }

  void setOnline(bool value) {
    online = value;
    if (!value) cancel();
    onChanged?.call();
    notifyListeners();
  }

  void remember(Json model) {
    installed.removeWhere((m) => m['id'] == model['id']);
    installed.add(Json.from(model));
    onChanged?.call();
    notifyListeners();
  }

  void cancel() {
    _cancelled = true;
    _client?.close(force: true);
  }

  void _check() {
    if (!online || _cancelled) {
      throw const HttpException('Network operation cancelled');
    }
  }

  Future<HttpClientResponse> _get(Uri uri) async {
    _check();
    // Handle redirects ourselves so downloads never downgrade to plaintext.
    for (var i = 0; i < 8; i++) {
      if (uri.scheme != 'https') throw const HttpException('HTTPS required');
      final request = await _client!
          .getUrl(uri)
          .timeout(const Duration(seconds: 30));
      request.followRedirects = false;
      final response = await request.close().timeout(
        const Duration(seconds: 30),
      );
      _check();
      if ([301, 302, 303, 307, 308].contains(response.statusCode)) {
        final location = response.headers.value(HttpHeaders.locationHeader);
        await response.drain<void>();
        if (location == null) throw const HttpException('Missing redirect');
        uri = uri.resolve(location);
        continue;
      }
      if (response.statusCode != 200) {
        throw HttpException('Download returned HTTP ${response.statusCode}');
      }
      return response;
    }
    throw const HttpException('Too many redirects');
  }

  Future<DiscoveryPage> _page(Uri uri) async {
    final response = await _get(uri);
    final bytes = <int>[];
    await for (final chunk in response.timeout(const Duration(seconds: 30))) {
      _check();
      if (bytes.length + chunk.length > 2 * 1024 * 1024) {
        throw const FormatException('Catalog response too large');
      }
      bytes.addAll(chunk);
    }
    final link = response.headers.value('link');
    final next = link == null
        ? null
        : RegExp(r'<([^>]+)>;\s*rel="?next"?').firstMatch(link)?.group(1);
    return DiscoveryPage(
      jsonDecode(utf8.decode(bytes)),
      next == null ? null : uri.resolve(next),
    );
  }

  Future<void> refresh() => _run(() async {
    refreshing = true;
    notifyListeners();
    var curated = catalog
        .where((a) => a.data['source'] != 'hf-discovery')
        .toList();
    var found = catalog
        .where((a) => a.data['source'] == 'hf-discovery')
        .toList();
    final failures = <String>[];
    try {
      final parsed = ModelLibrary();
      parsed.readCatalog(jsonEncode((await _page(catalogUrl)).data));
      curated = parsed.catalog;
    } catch (e) {
      _check();
      failures.add('Catalog update failed; retained cached entries: $e');
    }
    final cachedFound = List<ModelArtifact>.of(found);
    final cachedUnavailable = List<Json>.of(unavailable);
    final discovery = HfModelDiscovery(_page);
    try {
      await discovery.discover(
        Json.from(
          jsonDecode(await rootBundle.loadString('assets/profile.json')),
        ),
      );
      found = discovery.artifacts.map(ModelArtifact.new).toList();
      discovered = discovery.repositories;
      unavailable = discovery.unavailable;
    } catch (e) {
      _check();
      failures.add('HF discovery failed; retained cached discoveries: $e');
    }
    for (final repo in userRepositories) {
      if (isOfficialMimirGgufRepository(repo)) continue;
      final custom = HfModelDiscovery(_page);
      try {
        await custom.discoverRepository(
          repo,
          Json.from(
            jsonDecode(await rootBundle.loadString('assets/profile.json')),
          ),
          userSupplied: true,
        );
        found.removeWhere(
          (a) => a.data['repo'].toString().toLowerCase() == repo.toLowerCase(),
        );
        found.addAll(custom.artifacts.map(ModelArtifact.new));
        unavailable.removeWhere(
          (a) => a['repo'].toString().toLowerCase() == repo.toLowerCase(),
        );
        unavailable.addAll(custom.unavailable);
        if (!discovered.contains(repo)) discovered.add(repo);
      } catch (e) {
        _check();
        found.removeWhere(
          (a) => a.data['repo'].toString().toLowerCase() == repo.toLowerCase(),
        );
        unavailable.removeWhere(
          (a) => a['repo'].toString().toLowerCase() == repo.toLowerCase(),
        );
        found.addAll(
          cachedFound.where(
            (a) =>
                a.data['repo'].toString().toLowerCase() == repo.toLowerCase(),
          ),
        );
        unavailable.addAll(
          cachedUnavailable.where(
            (a) => a['repo'].toString().toLowerCase() == repo.toLowerCase(),
          ),
        );
        failures.add('$repo discovery failed; retained cached entries: $e');
      }
    }
    _check();
    // Curated qualification/profile wins for duplicate content or the same file.
    final curatedFiles = curated
        .map((a) => '${a.data['repo']}/${a.data['file']}')
        .toSet();
    final merged = <String, ModelArtifact>{};
    for (final artifact in [
      ...curated,
      ...found.where(
        (a) => !curatedFiles.contains('${a.data['repo']}/${a.data['file']}'),
      ),
    ]) {
      merged.putIfAbsent(artifact.id, () => artifact);
    }
    catalog = merged.values.toList();
    error = failures.isEmpty ? null : failures.join('\n');
    onChanged?.call();
  });

  Future<void> download(ModelArtifact artifact) => _run(() async {
    if (!allowsRepository(artifact.data['repo'])) {
      throw const FormatException(
        'Only official or explicitly added repositories are supported for downloading',
      );
    }
    downloading = artifact.id;
    received = 0;
    notifyListeners();
    final folder = Directory(p.join(directory!.path, 'models'));
    await folder.create(recursive: true);
    final target = File(p.join(folder.path, '${artifact.id}.gguf'));
    final partial = File('${target.path}.part');
    IOSink? sink;
    try {
      if (await target.exists()) {
        if (await target.length() != artifact.bytes ||
            (await sha256.bind(target.openRead()).first).toString() !=
                artifact.id) {
          throw const FormatException(
            'Existing model is damaged. Remove it before downloading.',
          );
        }
        _check();
        remember({...artifact.data, 'path': target.path, 'bundled': false});
        return;
      }
      final response = await _get(artifact.url);
      if (response.contentLength >= 0 &&
          response.contentLength != artifact.bytes) {
        throw const FormatException('Unexpected download size');
      }
      sink = partial.openWrite();
      var lastUpdate = DateTime.now();
      await for (final chunk in response.timeout(const Duration(seconds: 60))) {
        _check();
        received += chunk.length;
        if (received > artifact.bytes) {
          throw const FormatException('Download too large');
        }
        sink.add(chunk);
        // Apply disk backpressure instead of buffering gigabytes in memory.
        await sink.flush();
        if (DateTime.now().difference(lastUpdate).inMilliseconds > 150) {
          lastUpdate = DateTime.now();
          notifyListeners();
        }
      }
      await sink.close();
      sink = null;
      _check();
      if (received != artifact.bytes ||
          (await sha256.bind(partial.openRead()).first).toString() !=
              artifact.id) {
        throw const FormatException('Model checksum or size does not match');
      }
      final handle = await partial.open();
      final magic = await handle.read(4);
      await handle.close();
      if (!listEquals(magic, [71, 71, 85, 70])) {
        throw const FormatException('Not a GGUF model');
      }
      _check();
      if (await target.exists()) {
        throw const FileSystemException(
          'Model was installed while downloading. Retry to verify it.',
        );
      }
      await partial.rename(target.path);
      remember({...artifact.data, 'path': target.path, 'bundled': false});
    } finally {
      await sink?.close();
      if (await partial.exists()) await partial.delete();
    }
  });

  Future<void> _run(Future<void> Function() action) async {
    if (_work != null) return;
    if (!online) {
      error = 'Enable model downloads and discovery first.';
      notifyListeners();
      return;
    }
    _cancelled = false;
    error = null;
    _client = clientFactory()..connectionTimeout = const Duration(seconds: 30);
    final work = () async {
      try {
        await action();
      } catch (e) {
        error = _cancelled ? 'Cancelled.' : '$e';
      } finally {
        _client?.close(force: true);
        _client = null;
        downloading = null;
        refreshing = false;
        notifyListeners();
      }
    }();
    _work = work;
    await work;
    _work = null;
  }

  Future<void> close() async {
    cancel();
    await _work;
  }
}
