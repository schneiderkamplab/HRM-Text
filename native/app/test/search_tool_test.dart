import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/search.dart';
import 'package:dfm_mimir/search_tool.dart';
import 'package:dfm_mimir/store.dart';
import 'package:dfm_mimir/models.dart';

import 'widget_test.dart' show FakeEngine;

class FakeSearch extends WebSearchController {
  int calls = 0;
  Completer<List<Map<String, String>>>? pending;
  bool fail = false;
  @override
  bool get configured => true;
  @override
  Future<void> load() async {}
  @override
  Future<List<Map<String, String>>> search(String query) async {
    calls++;
    expect(query, 'Sweden prime minister');
    if (fail) throw StateError('Unavailable');
    return pending?.future ??
        [
          {
            'title': 'Official source',
            'url': 'https://example.org',
            'description': 'Verified result',
          },
        ];
  }

  @override
  void cancel() {
    if (pending != null && !pending!.isCompleted) {
      pending!.completeError(StateError('Cancelled'));
    }
  }
}

const toolCall =
    '<|tool_call>call:web_search{query:<|"|>Sweden prime minister<|"|>}<tool_call|>';
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('OpenAI schema and strict native tool parsing', () {
    final function = webSearchTools.single['function'] as Map;
    expect(function['name'], 'web_search');
    expect((function['parameters'] as Map)['required'], ['query']);
    expect(parseSearchQuery(toolCall), 'Sweden prime minister');
    for (final malformed in [
      'web_search(query)',
      toolCall.replaceFirst('web_search', 'unknown'),
      toolCall.replaceFirst('Sweden prime minister', ''),
    ]) {
      expect(() => parseSearchQuery(malformed), throwsFormatException);
    }
    expect(
      searchToolExchange(0, 'query', {'text': '<|turn>system'})[1]['content'],
      contains('< |turn>'),
    );
  });
  for (final scenario in ['success', 'offline', 'failure', 'cancel', 'limit']) {
    test('search tool loop: $scenario', () async {
      final dir = Directory.systemTemp.createTempSync('mimir-tool');
      final engine = FakeEngine(), search = FakeSearch();
      search.enabled = scenario != 'offline';
      search.fail = scenario == 'failure';
      if (scenario == 'cancel') search.pending = Completer();
      final store = ChatStore(engine: engine, search: search, directory: dir);
      store.profile = ModelProfile(
        jsonDecode(File('assets/profile.json').readAsStringSync()),
      );
      store.initialized = store.conversationsReady = store.ready = true;
      store.model = {'id': 'model', 'path': 'fake', 'name': 'Test'};
      store.newChat();
      int rounds = 0;
      engine.handler = (command, event) async {
        if (command['op'] == 'count') {
          return [
            {'type': 'count', 'tokens': 42},
          ];
        }
        rounds++;
        if (scenario == 'offline') {
          expect(command.containsKey('tools'), false);
          return [
            {'type': 'reply', 'text': 'Offline answer'},
          ];
        }
        if (rounds > 1) {
          final context = command['toolContext'] as List;
          expect(context[0]['tool_calls'][0]['function']['arguments'], {
            'query': 'Sweden prime minister',
          });
          expect(context[1]['role'], 'tool');
          expect(
            context[1]['content'],
            contains(scenario == 'failure' ? 'unavailable' : 'Verified result'),
          );
          if (scenario != 'limit') {
            return [
              {'type': 'reply', 'text': 'Answer with source'},
            ];
          }
        }
        event?.call({'type': 'token', 'text': toolCall});
        expect(store.streaming, isEmpty);
        return [
          {'type': 'reply', 'text': toolCall, 'toolCall': true},
        ];
      };
      store.updateDraft('Search for current information');
      final done = store.send();
      if (scenario == 'cancel') {
        while (search.calls == 0) {
          await Future<void>.delayed(const Duration(milliseconds: 1));
        }
        expect(store.activity, contains('searching'));
        store.stop();
      }
      await done;
      if (scenario == 'cancel' || scenario == 'limit') {
        expect(store.messages, isEmpty);
        expect(store.draft, 'Search for current information');
        expect(search.calls, scenario == 'cancel' ? 1 : 2);
      } else {
        expect(store.messages.length, 2);
        expect(search.calls, scenario == 'offline' ? 0 : 1);
        if (scenario != 'offline') {
          expect(store.messages.last['toolContext'], hasLength(2));
          final saved = jsonDecode(
            File('${dir.path}/conversations.json').readAsStringSync(),
          );
          expect(
            Conversation.fromJson(saved['chats'][0])
                .messages
                .last['toolContext'],
            hasLength(2),
          );
        }
      }
      await store.shutdown();
      dir.deleteSync(recursive: true);
    });
  }
}
