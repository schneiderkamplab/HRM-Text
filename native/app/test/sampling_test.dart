import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:dfm_mimir/store.dart';
import 'widget_test.dart' show FakeEngine, fixture;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('MixedLM defaults on; saved off and sampling values survive reopening', () async {
    final dir = await Directory.systemTemp.createTemp('mimir-sampling');
    addTearDown(() => dir.delete(recursive: true));
    final store = ChatStore(engine: FakeEngine(), directory: dir, manualStartup: true);
    await store.initialize();
    expect(store.mixedLM, true);
    expect(store.temperature, 0);
    expect(store.repetitionPenalty, 1);
    store.mixedLM = false;
    await store.setSampling(temperature: .7, repetitionPenalty: 1.15);
    final reopened = ChatStore(engine: FakeEngine(), directory: dir, manualStartup: true);
    await reopened.initialize();
    expect(reopened.mixedLM, false);
    expect(reopened.temperature, .7);
    expect(reopened.repetitionPenalty, 1.15);
    await reopened.setSampling(temperature: double.nan, repetitionPenalty: 1.2);
    expect(reopened.temperature, .7);
    await reopened.setSampling(temperature: .5, repetitionPenalty: .9);
    expect(reopened.repetitionPenalty, 1.15);
    final archive = File('${dir.path}/conversations.json');
    final data = jsonDecode(await archive.readAsString()) as Map<String, dynamic>;
    data.remove('mixedLM');
    data['temperature'] = 'bad';
    data['repetitionPenalty'] = 99;
    await archive.writeAsString(jsonEncode(data));
    final old = ChatStore(engine: FakeEngine(), directory: dir, manualStartup: true);
    await old.initialize();
    expect(old.mixedLM, true);
    expect(old.temperature, 0);
    expect(old.repetitionPenalty, 1);
  });
  test('chat forwards sampling values and disallows changes during generation', () async {
    final dir = await Directory.systemTemp.createTemp('mimir-sampling-command');
    addTearDown(() => dir.delete(recursive: true));
    final engine = FakeEngine();
    final store = fixture(engine, dir);
    await store.setSampling(temperature: .8, repetitionPenalty: 1.1);
    var sawReply = false;
    engine.handler = (command, _) async {
      if (command['op'] == 'count') return [{'type': 'count', 'tokens': 12}];
      expect(command['op'], 'reply');
      expect(command['temperature'], .8);
      expect(command['repeat_penalty'], 1.1);
      await store.setSampling(temperature: 1.2, repetitionPenalty: 1.5);
      expect(store.temperature, .8);
      sawReply = true;
      return [{'type': 'reply', 'text': 'Hej', 'cancelled': false, 'limited': false}];
    };
    store.updateDraft('Hej');
    await store.send();
    expect(sawReply, true);
    expect(store.notice, isNull);
    await store.save();
  });
}
