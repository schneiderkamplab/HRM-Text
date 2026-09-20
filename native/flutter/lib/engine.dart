import 'dart:async';
import 'dart:convert';
import 'dart:ffi';
import 'dart:io';
import 'dart:isolate';

import 'package:ffi/ffi.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;

typedef Json = Map<String, dynamic>;
String runtimePath() {
  final base = File(Platform.resolvedExecutable).parent.path;
  if (Platform.isMacOS) {
    return p.normalize(
      p.join(base, '../Frameworks/MimirRuntime.framework/MimirRuntime'),
    );
  }
  if (Platform.isIOS) {
    return p.join(base, 'Frameworks/MimirRuntime.framework/MimirRuntime');
  }
  return Platform.isWindows ? 'MimirRuntime.dll' : 'libMimirRuntime.so';
}

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
  return p.join(
    base,
    'Frameworks/App.framework/flutter_assets/assets/model.gguf',
  );
}

abstract class InferenceEngine {
  Future<List<Json>> command(Json command, {void Function(Json)? onEvent});
  void cancel();
  Future<void> close();
}

class NativeEngine implements InferenceEngine {
  late final DynamicLibrary _lib = DynamicLibrary.open(runtimePath());
  Pointer<Void>? _instance;
  Pointer<Void> get _handle => _instance ??= _lib
      .lookupFunction<Pointer<Void> Function(), Pointer<Void> Function()>(
        'mimir_create',
      )();
  late final _submit = _lib
      .lookupFunction<
        Int32 Function(Pointer<Void>, Pointer<Utf8>),
        int Function(Pointer<Void>, Pointer<Utf8>)
      >('mimir_submit');
  late final _poll = _lib
      .lookupFunction<
        Pointer<Utf8> Function(Pointer<Void>),
        Pointer<Utf8> Function(Pointer<Void>)
      >('mimir_poll');
  late final _free = _lib
      .lookupFunction<
        Void Function(Pointer<Utf8>),
        void Function(Pointer<Utf8>)
      >('mimir_free');
  late final _cancel = _lib
      .lookupFunction<
        Void Function(Pointer<Void>),
        void Function(Pointer<Void>)
      >('mimir_cancel');
  Future<void> _tail = Future.value();
  bool _closing = false;
  @override
  Future<List<Json>> command(Json command, {void Function(Json)? onEvent}) {
    if (_closing) return Future.error(StateError('Engine is closing'));
    final result = _tail.then((_) => _execute(command, onEvent));
    _tail = result.then<void>((_) {}, onError: (Object _, StackTrace _) {});
    return result;
  }

  Future<List<Json>> _execute(Json c, void Function(Json)? onEvent) async {
    if (_handle == nullptr) {
      throw StateError('Could not create inference engine');
    }
    final input = jsonEncode(c).toNativeUtf8();
    try {
      if (_submit(_handle, input) != 1) {
        throw StateError('Engine rejected operation');
      }
    } finally {
      calloc.free(input);
    }
    final events = <Json>[];
    String? error;
    for (;;) {
      final pointer = _poll(_handle);
      if (pointer == nullptr) {
        await Future<void>.delayed(const Duration(milliseconds: 16));
        continue;
      }
      late Json event;
      try {
        event = jsonDecode(pointer.toDartString()) as Json;
      } finally {
        _free(pointer);
      }
      if (event['type'] == 'done') break;
      if (event['type'] == 'error') error = event['message'] as String;
      // Do not retain every streamed chunk after it has been consumed by the UI.
      if (event['type'] != 'token' && event['type'] != 'summary') {
        events.add(event);
      }
      try {
        onEvent?.call(event);
      } catch (e) {
        error ??= 'Could not process engine event: $e';
        _cancel(_handle);
        // Drain through done before allowing another native command.
      }
    }
    if (error != null) throw StateError(error);
    return events;
  }

  @override
  void cancel() {
    if (!_closing && _instance != null && _instance != nullptr) {
      _cancel(_instance!);
    }
  }

  @override
  Future<void> close() async {
    if (_closing) return;
    cancel();
    _closing = true;
    await _tail;
    final handle = _instance;
    if (handle == null || handle == nullptr) return;
    final address = handle.address;
    final path = runtimePath();
    await Isolate.run(() {
      DynamicLibrary.open(path).lookupFunction<
        Void Function(Pointer<Void>),
        void Function(Pointer<Void>)
      >('mimir_destroy')(Pointer.fromAddress(address));
    });
  }
}
