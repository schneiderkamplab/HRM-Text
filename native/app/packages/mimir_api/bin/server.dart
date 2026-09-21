import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;

import 'package:mimir_api/native_engine.dart';
import 'package:mimir_api/api/server.dart';

Future<void> main(List<String> arguments) async {
  NativeEngine? engine;
  LocalApiServer? server;
  final signals = <StreamSubscription<ProcessSignal>>[];
  try {
    if (arguments.contains('--help')) {
      stdout.writeln(
        'DFM Mimir headless API server\n'
        'Usage: dfm-mimir-server [--model GGUF] [--profile JSON] [--library FILE]\n'
        '  [--device auto|cpu|DEVICE] [--context TOKENS] [--max-tokens TOKENS] [--port PORT]\n'
        'Listens on 127.0.0.1 only. Set MIMIR_API_KEY for Bearer authentication.\n'
        'Defaults to the packaged model/profile; no GUI/display required.',
      );
      return;
    }
    const flags = {
      '--model',
      '--profile',
      '--library',
      '--device',
      '--context',
      '--max-tokens',
      '--port',
    };
    final options = <String, String>{};
    for (var i = 0; i < arguments.length; i += 2) {
      if (!flags.contains(arguments[i]) ||
          i + 1 >= arguments.length ||
          options.containsKey(arguments[i])) {
        throw FormatException(
          'Unknown, duplicate or incomplete option: ${arguments[i]}',
        );
      }
      options[arguments[i]] = arguments[i + 1];
    }
    final executable = File(Platform.resolvedExecutable).parent.path;
    final assets = Platform.isMacOS
        ? p.normalize(
            p.join(
              executable,
              '../Frameworks/App.framework/Resources/flutter_assets/assets',
            ),
          )
        : p.join(executable, 'data/flutter_assets/assets');
    final model = File(options['--model'] ?? p.join(assets, 'model.gguf'));
    final profile =
        jsonDecode(
              await File(
                options['--profile'] ?? p.join(assets, 'profile.json'),
              ).readAsString(),
            )
            as Json;
    final port = int.parse(options['--port'] ?? '8080');
    if (port < 1 || port > 65535) {
      throw const FormatException('Port must be 1–65535');
    }
    engine = NativeEngine(libraryPath: options['--library']);
    final stopped = Completer<void>();
    for (final signal in [
      ProcessSignal.sigint,
      if (!Platform.isWindows) ProcessSignal.sigterm,
    ]) {
      signals.add(
        signal.watch().listen((_) {
          engine?.cancel();
          if (!stopped.isCompleted) stopped.complete();
        }),
      );
    }
    final loaded = await engine.command({
      'op': 'load',
      'path': model.absolute.path,
      'modelBytes': await model.length(),
      'profile': profile,
      'device': options['--device'] ?? 'auto',
      'context': int.parse(options['--context'] ?? '0'),
      'mixedLM': false,
    });
    final state = loaded.firstWhere((e) => e['type'] == 'loaded');
    final context = state['context'] as int;
    final budget = int.parse(options['--max-tokens'] ?? '512');
    if (budget < 1 || budget >= context) {
      throw const FormatException('Invalid default reply budget');
    }
    if (stopped.isCompleted) return;
    server = LocalApiServer(
      engine: engine,
      ready: () => !stopped.isCompleted,
      context: () => context,
      budget: () => budget,
      apiKey: Platform.environment['MIMIR_API_KEY'],
    );
    await server.start(port: port);
    stdout.writeln(
      'DFM Mimir API: ${server.address} · ${state['device']} · context $context',
    );
    await stopped.future;
  } catch (error) {
    stderr.writeln('DFM Mimir server: $error');
    exitCode = 1;
  } finally {
    await server?.stop();
    await engine?.close();
    for (final signal in signals) {
      await signal.cancel();
    }
  }
}
