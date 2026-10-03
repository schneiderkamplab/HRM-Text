import 'dart:async';

import 'package:dfm_mimir/network.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

class PendingClient extends http.BaseClient {
  final response = Completer<http.StreamedResponse>();
  final aborted = Completer<void>();
  http.BaseRequest? request;
  int closes = 0;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    this.request = request;
    (request as http.Abortable).abortTrigger!.then((_) {
      aborted.complete();
      if (!response.isCompleted) {
        response.completeError(http.RequestAbortedException(request.url));
      }
    });
    return response.future;
  }

  @override
  void close() => closes++;
}

void main() {
  test('cancels pending requests and prevents reuse without forwarding credentials', () async {
    final client = PendingClient();
    final session = NetworkSession(client);
    final pending = session.send(
      'POST',
      Uri.https('example.com', '/search'),
      headers: {'authorization': 'Bearer test'},
      body: [1, 2],
    );
    final expectation = expectLater(
      pending,
      throwsA(isA<http.RequestAbortedException>()),
    );
    expect(client.request!.followRedirects, false);
    expect((client.request as http.Request).bodyBytes, [1, 2]);
    session.close();
    session.close();
    await client.aborted.future;
    await expectation;
    expect(client.closes, 1);
    expect(
      () => session.send('GET', Uri.https('example.com')),
      throwsStateError,
    );
  });

  test('abort trigger stays active after response headers arrive', () async {
    final client = PendingClient();
    final session = NetworkSession(client);
    final pending = session.send('GET', Uri.https('example.com', '/model'));
    client.response.complete(http.StreamedResponse(const Stream.empty(), 200));
    await pending;
    session.close();
    await client.aborted.future;
    expect(client.closes, 1);
  });
}
