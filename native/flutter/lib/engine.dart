import 'dart:io';

import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;

export 'package:mimir_api/native_engine.dart';

Future<String> bundledModelPath() async {
  if (Platform.isAndroid) {
    // Copy from the APK using native streaming I/O, not a gigabyte Dart buffer.
    return (await const MethodChannel('dk.sdu.mimir/assets')
        .invokeMethod<String>('bundledModelPath'))!;
  }
  final base = File(Platform.resolvedExecutable).parent.path;
  if (Platform.isMacOS) {
    return p.normalize(
      p.join(
        base,
        '../Frameworks/App.framework/Resources/flutter_assets/assets/model.gguf',
      ),
    );
  }
  if (Platform.isLinux || Platform.isWindows) {
    return p.join(base, 'data', 'flutter_assets', 'assets', 'model.gguf');
  }
  return p.join(
    base,
    'Frameworks/App.framework/flutter_assets/assets/model.gguf',
  );
}
