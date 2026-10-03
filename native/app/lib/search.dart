import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'network.dart';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const searchEndpoint =
    'https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev/v1/search';
const searchCredentialName = 'mimir-search-key';

class WebSearchController extends ChangeNotifier {
  WebSearchController({
    FlutterSecureStorage? storage,
    Uri? endpoint,
    http.Client Function()? clientFactory,
  }) : clientFactory = clientFactory ?? createNetworkClient,
       storage =
           storage ??
           const FlutterSecureStorage(
             mOptions: MacOsOptions(usesDataProtectionKeychain: false),
           ),
       endpoint = endpoint ?? Uri.parse(searchEndpoint);
  final FlutterSecureStorage storage;
  final Uri endpoint;
  final http.Client Function() clientFactory;
  bool enabled = false, busy = false;
  String _key = '';
  bool get configured => _key.isNotEmpty;
  // The app's Mimir credential only; Jina credentials stay in the Worker.
  String get configuredKey => _key;
  String? message;
  Future<void>? _loading;
  NetworkSession? _client;
  int _revision = 0;
  static bool validKey(String value) =>
      RegExp(r'^mimir_[a-f0-9]{6,128}$').hasMatch(value);

  Future<void> load() => _loading ??= _load();
  Future<void> _load() async {
    try {
      _key = await storage.read(key: searchCredentialName) ?? '';
    } catch (_) {
      message = 'Secure key storage is unavailable. You can use a key for this session.';
    }
    notifyListeners();
  }

  Future<void> setKey(String value, {required bool remember}) async {
    await load();
    value = value.trim();
    if (value.isNotEmpty && !validKey(value)) {
      throw const FormatException(
        'Use mimir_ followed by 6–128 lowercase hexadecimal characters.',
      );
    }
    _key = value;
    message = null;
    try {
      if (remember && value.isNotEmpty) {
        await storage.write(key: searchCredentialName, value: value);
      } else {
        await storage.delete(key: searchCredentialName);
      }
    } catch (_) {
      message = 'Key changed for this session only. Secure storage could not be updated.';
    }
    notifyListeners();
  }

  void setEnabled(bool value) {
    enabled = value;
    if (!value) cancel();
    notifyListeners();
  }

  Future<List<Map<String, String>>> search(String query) async {
    if (!enabled) throw StateError('Enable online search in settings first.');
    if (busy) throw StateError('A search is already running.');
    query = query.trim();
    if (query.isEmpty || query.length > 2000) {
      throw const FormatException('Enter a query of 1–2000 characters.');
    }
    final revision = _revision;
    await load();
    if (revision != _revision) throw StateError('Search cancelled.');
    if (busy) throw StateError('A search is already running.');
    if (!configured) throw StateError('Enter a search key in settings first.');
    if (!enabled) throw StateError('Online search is off.');
    busy = true;
    notifyListeners();
    final client = NetworkSession(clientFactory());
    _client = client;
    final timer = Timer(const Duration(seconds: 40), () => client.close());
    try {
      final response = await client.send(
        'POST',
        endpoint,
        headers: {
          'content-type': 'application/json',
          'authorization': 'Bearer $_key',
        },
        body: utf8.encode(jsonEncode({'query': query})),
      );
      if (response.statusCode != 200) {
        throw StateError(switch (response.statusCode) {
          401 => 'Search key is invalid or disabled.',
          429 => 'Search limit reached. Please try again later.',
          _ => 'Search is unavailable. Please try again later.',
        });
      }
      final bytes = <int>[];
      await for (final chunk in response.stream) {
        if (bytes.length + chunk.length > 65536) {
          throw const FormatException('Search response too large.');
        }
        bytes.addAll(chunk);
      }
      final data = jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
      return (data['results'] as List)
          .take(5)
          .map(
            (r) => {
              'title': r['title'] as String,
              'url': r['url'] as String,
              'description': r['description'] as String,
            },
          )
          .toList();
    } on StateError {
      rethrow;
    } catch (_) {
      throw StateError('Search failed. Check your connection and try again.');
    } finally {
      timer.cancel();
      client.close();
      _client = null;
      busy = false;
      notifyListeners();
    }
  }

  void cancel() {
    _revision++;
    _client?.close();
  }
}
