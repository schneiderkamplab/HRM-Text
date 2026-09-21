import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:uuid/uuid.dart';

import 'models.dart';

const feedbackPolicyVersion = '2026-09-20';
const feedbackContact = 'petersk@imada.sdu.dk';
const feedbackMaxBytes = 1024 * 1024;
// Public intake URL only. No credentials belong in the app.
const feedbackEndpoint = String.fromEnvironment(
  'MIMIR_FEEDBACK_URL',
  defaultValue:
      'https://dfm-mimir-feedback.dfm-mimir-feedback.workers.dev/v1/feedback',
);

class FeedbackSnapshot {
  final String _json;
  FeedbackSnapshot({
    required Conversation conversation,
    required String appVersion,
    required int contextTokens,
    required int replyTokens,
    required bool mixedLM,
  }) : _json = jsonEncode({
         'chat': {
           'messages': conversation.messages
               .map((m) => {'role': m['role'], 'content': m['content']})
               .toList(),
           'summary': conversation.memory == null
               ? null
               : {
                   'content': conversation.memory!['summary'],
                   'coveredMessages': conversation.memory!['covered'],
                 },
         },
         'metadata': {
           'appVersion': appVersion,
           'platform': Platform.operatingSystem,
           'modelId': conversation.modelID ?? '',
           'contextTokens': contextTokens,
           'replyTokens': replyTokens,
           'mixedLM': mixedLM,
         },
       });

  Map<String, dynamic> payload({
    required String id,
    required String rating,
    required String pseudonym,
    required String comment,
    required bool publication,
  }) => {
    'id': id,
    'policyVersion': feedbackPolicyVersion,
    'rating': rating,
    'pseudonym': pseudonym.trim(),
    'comment': comment,
    'consent': {
      'improvement': true,
      'publication': publication,
      'license': publication ? 'CC-BY-4.0' : null,
    },
    ...jsonDecode(_json) as Map<String, dynamic>,
  };
}

class FeedbackIdentity {
  final File file;
  FeedbackIdentity(Directory directory)
    : file = File('${directory.path}/feedback-pseudonym.txt');
  static String generate() {
    const adjectives = [
      'Amber',
      'Bright',
      'Calm',
      'Copper',
      'Gentle',
      'Golden',
      'Quiet',
      'Silver',
    ];
    const animals = [
      'Badger',
      'Falcon',
      'Fox',
      'Heron',
      'Otter',
      'Owl',
      'Raven',
      'Seal',
    ];
    final random = Random.secure();
    final suffix = List.generate(
      4,
      (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0'),
    ).join();
    return '${adjectives[random.nextInt(adjectives.length)]}${animals[random.nextInt(animals.length)]}-$suffix';
  }

  Future<String> load() async {
    if (await file.exists()) {
      final saved = (await file.readAsString()).trim();
      if (saved.isNotEmpty && saved.length <= 80) return saved;
    }
    final value = generate();
    await save(value);
    return value;
  }

  Future<void> save(String value) async {
    await file.parent.create(recursive: true);
    await file.writeAsString(value.trim(), flush: true);
  }
}

class FeedbackFailure implements Exception {
  final String message;
  const FeedbackFailure(this.message);
  @override
  String toString() => message;
}

class FeedbackClient {
  final Uri endpoint;
  final Duration timeout;
  FeedbackClient(
    this.endpoint, {
    this.timeout = const Duration(seconds: 30),
    bool allowLoopback = false,
  }) {
    if (endpoint.scheme != 'https' &&
        !(allowLoopback &&
            endpoint.scheme == 'http' &&
            ['127.0.0.1', '::1', 'localhost'].contains(endpoint.host))) {
      throw ArgumentError('Feedback requires HTTPS');
    }
  }
  Future<String> submit(String body) async {
    final bytes = utf8.encode(body);
    if (bytes.length > feedbackMaxBytes) {
      throw const FeedbackFailure(
        'This chat exceeds the 1 MiB feedback limit.',
      );
    }
    final client = HttpClient()..connectionTimeout = timeout;
    try {
      return await (() async {
        final request = await client.postUrl(endpoint);
        request.followRedirects = false;
        request.headers.contentType = ContentType.json;
        request.contentLength = bytes.length;
        request.add(bytes);
        final response = await request.close();
        if (response.statusCode != 200 && response.statusCode != 201) {
          throw FeedbackFailure(switch (response.statusCode) {
            413 => 'This chat is too large to send.',
            429 => 'Too many submissions. Please retry later.',
            409 =>
              'This submission ID is already used. Close and reopen feedback.',
            400 => 'The service could not accept this feedback. Check the preview or update the app.',
            _ => 'Feedback service unavailable. Please retry later.',
          });
        }
        final data = <int>[];
        await for (final chunk in response) {
          data.addAll(chunk);
          if (data.length > 8192) {
            throw const FormatException('Oversized receipt');
          }
        }
        final receipt = jsonDecode(utf8.decode(data));
        if (receipt['id'] != jsonDecode(body)['id'] ||
            receipt['receivedAt'] is! String) {
          throw const FormatException('Invalid receipt');
        }
        return receipt['id'] as String;
      })().timeout(timeout);
    } on FeedbackFailure {
      rethrow;
    } catch (_) {
      throw const FeedbackFailure(
        'Delivery could not be confirmed. Retry safely with the same submission, or copy it for later.',
      );
    } finally {
      client.close(force: true);
    }
  }
}

// Keep the same receipt ID for exact retries, even after uncertain network failure.
class FeedbackDraft {
  String? _content;
  String _id = const Uuid().v4();
  String encode(
    FeedbackSnapshot snapshot, {
    required String rating,
    required String pseudonym,
    required String comment,
    required bool publication,
  }) {
    final p = snapshot.payload(
      id: '',
      rating: rating,
      pseudonym: pseudonym,
      comment: comment,
      publication: publication,
    );
    final content = jsonEncode(p);
    if (_content != null && _content != content) _id = const Uuid().v4();
    _content = content;
    p['id'] = _id;
    return const JsonEncoder.withIndent('  ').convert(p);
  }
}
