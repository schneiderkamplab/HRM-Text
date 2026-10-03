import 'dart:async';
import 'dart:io';

import 'package:cupertino_http/cupertino_http.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

/// Apple HTTPS uses URLSession; other platforms retain Dart's HTTP transport.
http.Client createNetworkClient() {
  if (Platform.isIOS || Platform.isMacOS) {
    final config = URLSessionConfiguration.ephemeralSessionConfiguration()
      ..httpShouldSetCookies = false
      ..requestCachePolicy =
          NSURLRequestCachePolicy.NSURLRequestReloadIgnoringLocalCacheData
      ..timeoutIntervalForRequest = const Duration(seconds: 30);
    return CupertinoClient.fromSessionConfiguration(config);
  }
  return IOClient(
    HttpClient()..connectionTimeout = const Duration(seconds: 30),
  );
}

/// One cancellable operation, including all redirects and response streaming.
class NetworkSession {
  NetworkSession(http.Client client) : _client = client;
  final http.Client _client;
  final _abort = Completer<void>();

  Future<http.StreamedResponse> send(
    String method,
    Uri uri, {
    Map<String, String> headers = const {},
    List<int>? body,
  }) {
    if (_abort.isCompleted) throw StateError('Network operation cancelled');
    final request =
        http.AbortableRequest(method, uri, abortTrigger: _abort.future)
          ..followRedirects = false
          ..headers.addAll(headers);
    if (body != null) request.bodyBytes = body;
    return _client.send(request);
  }

  void close() {
    if (_abort.isCompleted) return;
    // CupertinoClient.close alone lets active tasks finish. Abort explicitly.
    _abort.complete();
    _client.close();
  }
}
