import 'dart:convert';
import 'dart:io';

import 'package:integration_test/integration_test_driver.dart';

Future<void> main() async {
  final output = Platform.environment['MIMIR_SCREENSHOT_DIR'];
  if (output == null) {
    throw StateError('Set MIMIR_SCREENSHOT_DIR to a fresh capture directory');
  }
  final directory = Directory(output);
  if (await directory.exists()) {
    throw StateError('Capture directory already exists: $output');
  }
  await directory.create(recursive: true);
  await integrationDriver(
    timeout: const Duration(minutes: 30),
    writeResponseOnFailure: true,
    responseDataCallback: (data) async {
      if (data == null) return;
      final metadata = Map<String, dynamic>.from(data);
      final captures = Map<String, dynamic>.from(
        metadata.remove('captures') as Map? ?? {},
      );
      for (final entry in captures.entries) {
        await File('$output/${entry.key}.png')
            .writeAsBytes(base64Decode(entry.value as String));
      }
      metadata['files'] = captures.keys.toList();
      await File('$output/capture.json')
          .writeAsString(const JsonEncoder.withIndent('  ').convert(metadata));
    },
  );
}
