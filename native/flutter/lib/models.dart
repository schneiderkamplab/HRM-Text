import 'engine.dart';

import 'package:uuid/uuid.dart';

class ModelProfile {
  final Json data;
  ModelProfile(this.data) {
    validate();
  }
  int number(String key) => (data[key] as num).toInt();
  String get name => data['name'] as String;
  void validate() {
    final min = number('minimumContext'), max = number('maximumContext');
    final reserve = number('promptReserve');
    final tiers = (data['contextTiers'] as List).cast<int>();
    final fraction = (data['memoryFraction'] as num).toDouble();
    if (data['version'] != 1 ||
        name.isEmpty ||
        min < 1 ||
        max < min ||
        max > 2147483647 ||
        reserve < 1 ||
        reserve >= min ||
        number('minimumReply') < 1 ||
        number('minimumReply') > min - reserve ||
        number('maximumDefaultReply') < number('minimumReply') ||
        number('maximumDefaultReply') > max - reserve ||
        number('replyContextDivisor') < 1 ||
        number('threads') < 1 ||
        number('threads') > 256 ||
        number('memoryBytesPerToken') <= 0 ||
        number('fixedMemoryBytes') < 0 ||
        number('cpuAttentionBytesPerTokenSquared') < 0 ||
        !fraction.isFinite ||
        fraction <= 0 ||
        fraction > 1 ||
        tiers.isEmpty ||
        tiers.first != min ||
        tiers.last != max ||
        List.generate(
          tiers.length - 1,
          (i) => tiers[i] >= tiers[i + 1],
        ).contains(true) ||
        data['systemPrompt'] is! String) {
      throw const FormatException('Invalid model profile');
    }
  }

  String? limitsError(int context, int reply) {
    if (context < number('minimumContext') ||
        context > number('maximumContext')) {
      return 'Context must be ${number('minimumContext')}–${number('maximumContext')} tokens.';
    }
    if (reply < 1 || reply > context - number('promptReserve')) {
      return 'Reply must leave ${number('promptReserve')} tokens for the prompt.';
    }
    return null;
  }

  int defaultReply(int context) => (context ~/ number('replyContextDivisor'))
      .clamp(number('minimumReply'), number('maximumDefaultReply'))
      .clamp(1, context - number('promptReserve'));
}

class Conversation {
  String id, title;
  String? modelID;
  DateTime updated;
  List<Json> messages;
  Json? memory;
  Conversation({
    String? id,
    this.title = 'New chat',
    this.modelID,
    DateTime? updated,
    List<Json>? messages,
    this.memory,
  }) : id = id ?? const Uuid().v4(),
       updated = updated ?? DateTime.now(),
       messages = messages ?? [];
  factory Conversation.fromJson(Json j) {
    final c = Conversation(
      id: j['id'],
      title: j['title'],
      modelID: j['modelID'],
      updated: DateTime.parse(j['updated']),
      messages: (j['messages'] as List)
          .map((m) => Json.from(m as Map))
          .toList(),
      memory: j['memory'] == null ? null : Json.from(j['memory']),
    );
    if (c.messages.length.isOdd) {
      throw const FormatException('Incomplete saved turn');
    }
    for (var i = 0; i < c.messages.length; i++) {
      if (c.messages[i]['role'] != (i.isEven ? 'user' : 'assistant') ||
          c.messages[i]['content'] is! String) {
        throw const FormatException('Invalid conversation');
      }
    }
    if (c.memory != null) {
      final n = c.memory!['covered'] as int;
      if (n <= 0 ||
          n.isOdd ||
          n > c.messages.length ||
          (c.memory!['summary'] as String).isEmpty) {
        throw const FormatException('Invalid summary');
      }
    }
    return c;
  }
  Json toJson() => {
    'id': id,
    'title': title,
    'modelID': modelID,
    'updated': updated.toIso8601String(),
    'messages': messages,
    'memory': memory,
  };
}
