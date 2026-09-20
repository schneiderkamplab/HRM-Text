import '../native_engine.dart';

class ApiError implements Exception {
  final int status;
  final String message;
  ApiError(this.status, this.message);
}

Json completionCommand(
  Json body,
  String model,
  int context,
  int defaultBudget,
) {
  const supported = {
    'model',
    'messages',
    'stream',
    'stream_options',
    'max_tokens',
    'max_completion_tokens',
    'temperature',
    'top_p',
    'seed',
    'n',
  };
  for (final key in body.keys) {
    if (!supported.contains(key)) {
      throw ApiError(400, 'Unsupported parameter: $key');
    }
  }
  if (body['model'] != model) {
    throw ApiError(404, 'Unknown model. Use GET /v1/models.');
  }
  if (body.containsKey('stream') && body['stream'] is! bool) {
    throw ApiError(400, 'stream must be boolean');
  }
  if (body.containsKey('n') && body['n'] != 1) {
    throw ApiError(400, 'Only n=1 is supported');
  }
  final options = body['stream_options'];
  if (options != null &&
      (options is! Map ||
          options.keys.any((k) => k != 'include_usage') ||
          (options.containsKey('include_usage') &&
              options['include_usage'] is! bool))) {
    throw ApiError(400, 'Only stream_options.include_usage is supported');
  }
  if (body.containsKey('max_tokens') &&
      body.containsKey('max_completion_tokens')) {
    throw ApiError(400, 'Specify one token budget');
  }
  final budget =
      body['max_completion_tokens'] ?? body['max_tokens'] ?? defaultBudget;
  if (budget is! int || budget < 1 || budget >= context) {
    throw ApiError(400, 'Token budget must be between 1 and ${context - 1}');
  }
  final temperature = body['temperature'] ?? 0;
  final topP = body['top_p'] ?? 1;
  final seed = body['seed'] ?? 0;
  if (temperature is! num ||
      !temperature.isFinite ||
      temperature < 0 ||
      temperature > 2 ||
      topP is! num ||
      !topP.isFinite ||
      topP <= 0 ||
      topP > 1 ||
      seed is! int ||
      seed < 0 ||
      seed >= 0xffffffff) {
    throw ApiError(400, 'Invalid temperature, top_p or seed');
  }
  final raw = body['messages'];
  if (raw is! List || raw.isEmpty) {
    throw ApiError(400, 'messages must be a nonempty array');
  }
  final messages = <Json>[];
  for (final message in raw) {
    if (message is! Map ||
        message['content'] is! String ||
        message['role'] is! String ||
        message.keys.any((k) => k != 'role' && k != 'content')) {
      throw ApiError(
        400,
        'Only text messages with role and content are supported',
      );
    }
    messages.add(Map<String, dynamic>.from(message));
  }
  String? system;
  if (messages.first['role'] == 'system') {
    system = messages.removeAt(0)['content'];
  }
  if (messages.isEmpty || messages.length.isEven) {
    throw ApiError(400, 'Messages must end with a user turn');
  }
  for (var i = 0; i < messages.length; i++) {
    if (messages[i]['role'] != (i.isEven ? 'user' : 'assistant')) {
      throw ApiError(
        400,
        'Expected optional initial system message, then alternating user/assistant turns',
      );
    }
  }
  return {
    'op': 'completion',
    'history': messages.take(messages.length - 1).toList(),
    'prompt': messages.last['content'],
    'system': ?system,
    'budget': budget,
    'temperature': temperature,
    'top_p': topP,
    'seed': seed,
  };
}
