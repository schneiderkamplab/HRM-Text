// Build-time only: use the pinned Dart SDK's own Mach-O executable writer.
import 'package:code_assets/code_assets.dart' show OS;
import 'package:dart2native/dart2native.dart' show writeAppendedExecutable;

Future<void> main(List<String> arguments) async {
  if (arguments.length != 3) {
    throw ArgumentError('Expected runtime, AOT snapshot and output paths');
  }
  await writeAppendedExecutable(
    arguments[0],
    arguments[1],
    arguments[2],
    OS.macOS,
  );
}
