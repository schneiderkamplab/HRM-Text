import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

import 'dart:ui' show AppExitResponse;

import 'store.dart';
import 'chat_view.dart';
import 'text_scaling.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  LicenseRegistry.addLicense(() async* {
    for (final name in ['DFM-Mimir', 'Mimir', 'llama.cpp', 'HRM-Text']) {
      yield LicenseEntryWithLineBreaks([
        name,
      ], await rootBundle.loadString('assets/licenses/$name.txt'));
    }
  });
  runApp(MimirApp(store: ChatStore()));
}

class MimirApp extends StatefulWidget {
  final ChatStore store;
  const MimirApp({super.key, required this.store});
  @override
  State<MimirApp> createState() => _MimirAppState();
}

class _MimirAppState extends State<MimirApp> {
  late final AppLifecycleListener lifecycle;
  @override
  void initState() {
    super.initState();
    lifecycle = AppLifecycleListener(
      onHide: widget.store.stop,
      onPause: widget.store.stop,
      onExitRequested: () async {
        await widget.store.shutdown();
        return AppExitResponse.exit;
      },
    );
    widget.store.initialize();
  }

  @override
  void dispose() {
    lifecycle.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'DFM Mimir',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xffb70610)),
      useMaterial3: true,
    ),
    darkTheme: ThemeData(
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xffc62832),
        brightness: Brightness.dark,
      ),
      useMaterial3: true,
    ),
    builder: (context, child) => ListenableBuilder(
      listenable: widget.store,
      builder: (context, _) => MediaQuery(
        data: MediaQuery.of(context).copyWith(
          textScaler: AppTextScaler(
            MediaQuery.textScalerOf(context), widget.store.textScale,
          ),
        ),
        child: child!,
      ),
    ),
    home: ChatView(store: widget.store),
  );
}
