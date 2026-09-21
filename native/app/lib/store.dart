import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import 'engine.dart';
import 'models.dart';
import 'model_library.dart';

import 'package:mimir_api/api/server.dart';

class ChatStore extends ChangeNotifier {
  final InferenceEngine engine;
  Directory? directory;
  final bool manualStartup;
  String? _sessionDevice;
  ChatStore({InferenceEngine? engine, this.directory, bool? manualStartup})
    : manualStartup = manualStartup ?? Platform.isAndroid,
      engine = engine ?? NativeEngine();
  final ModelLibrary library = ModelLibrary();
  List<Conversation> chats = [];
  String? selected, notice;
  String draft = '',
      streaming = '',
      device = 'auto',
      engineLabel = 'Not loaded';
  String? pending;
  List<String> backendFallbackReasons = [];
  String actualBackend = '';
  Json? preview, model;
  late ModelProfile profile;
  bool conversationsReady = false;
  bool initialized = false,
      ready = false,
      loading = false,
      generating = false,
      compacting = false,
      closing = false;
  bool onlineFeedback = false;
  void setOnlineFeedback(bool enabled) {
    onlineFeedback = enabled;
    notifyListeners();
    save();
  }

  bool compact = true,
      mixedLM = false,
      showSummary = false,
      automatic = true,
      persistence = true;
  int context = 1024, reply = 512;
  int? training, used;
  int lastReusedTokens = 0;
  List<Json> devices = [];
  int _countRevision = 0;
  Future<void> _saving = Future.value();
  LocalApiServer? apiServer;
  bool apiBusy = false;
  int apiPort = 8080;
  bool get desktop =>
      Platform.isMacOS || Platform.isLinux || Platform.isWindows;
  bool get busy => loading || generating || closing || apiBusy;
  Future<void> setApiEnabled(bool enabled, {int? port}) async {
    if (!desktop) return;
    if (!enabled) {
      final previous = apiServer;
      apiServer = null;
      await previous?.stop();
      apiBusy = false;
      notifyListeners();
      return;
    }
    if (apiServer != null) return;
    try {
      late final LocalApiServer server;
      server = LocalApiServer(
        engine: engine,
        ready: () => ready && !loading && !closing,
        context: () => context,
        budget: () => reply,
        apiKey: Platform.environment['MIMIR_API_KEY'],
        onBusy: (value) {
          if (identical(apiServer, server)) {
            apiBusy = value;
            notifyListeners();
          }
        },
      );
      apiServer = server;
      apiPort = port ?? apiPort;
      await server.start(port: apiPort);
    } catch (error) {
      apiServer = null;
      notice = 'Could not start local API: $error';
    }
    notifyListeners();
  }

  // Restore the archive before allowing edits; inference loading is independent.
  bool get canCreateChat => conversationsReady && !generating && !closing;
  Conversation? get active => chats.where((c) => c.id == selected).firstOrNull;
  List<Json> get messages => active?.messages ?? [];
  bool get modelMatches => messages.isEmpty || active?.modelID == model?['id'];
  bool get canSend => ready && !busy && modelMatches && draft.trim().isNotEmpty;
  Json? get visibleSummary => showSummary ? (preview ?? active?.memory) : null;
  int? get summaryPosition => visibleSummary == null
      ? null
      : (visibleSummary!['position'] ?? visibleSummary!['covered'] as int)
                .clamp(0, messages.length)
            as int;
  String get activity =>
      compacting ? 'DFM Mimir is compacting…' : 'DFM Mimir is thinking…';
  void setNotice(String? value) {
    notice = value;
    notifyListeners();
  }

  void updateDraft(String text) {
    draft = text;
    notifyListeners();
  }

  Future<void> initialize() async {
    loading = true;
    notifyListeners();
    try {
      profile = ModelProfile(
        Json.from(
          jsonDecode(await rootBundle.loadString('assets/profile.json')),
        ),
      );
      directory ??= Directory(
        p.join((await getApplicationSupportDirectory()).path, 'DFM Mimir'),
      );
      await directory!.create(recursive: true);
      String? cachedCatalog;
      final file = File(p.join(directory!.path, 'conversations.json'));
      if (await file.exists()) {
        try {
          final j = jsonDecode(await file.readAsString()) as Json;
          if (j['version'] != 1) {
            throw const FormatException('Unknown archive version');
          }
          chats = (j['chats'] as List)
              .map((c) => Conversation.fromJson(Json.from(c)))
              .toList();
          if (chats.map((c) => c.id).toSet().length != chats.length) {
            throw const FormatException('Duplicate chats');
          }
          selected = j['selected'];
          onlineFeedback = j['onlineFeedback'] == true;
          compact = j['compact'] ?? true;
          mixedLM = j['mixedLM'] ?? false;
          showSummary = j['showSummary'] ?? false;
          automatic = j['automatic'] ?? true;
          context = j['context'] ?? 1024;
          reply = j['reply'] ?? 512;
          device = j['device'] ?? 'auto';
          model = j['model'];
          cachedCatalog = j['modelCatalog'] == null ? null : jsonEncode(j['modelCatalog']);
          library.setUserRepositories((j['userModelRepositories'] as List? ?? []).cast<String>());
          library.online = j['modelNetwork'] == true;
          library.installed = (j['installedModels'] as List? ?? [])
              .map((m) => Json.from(m)).toList();
          library.unavailable = (j['unavailableModels'] as List? ?? [])
              .map((m) => Json.from(m))
              .where((m) => library.allowsRepository(m['repo']))
              .toList();
          library.discovered = (j['discoveredModels'] as List? ?? [])
              .where(library.allowsRepository)
              .cast<String>()
              .toList();
          if (model?['profile'] != null) {
            profile = ModelProfile(Json.from(model!['profile']));
          }
          if (profile.limitsError(context, reply) != null) {
            automatic = true;
            context = profile.number('minimumContext');
            reply = profile.defaultReply(context);
          }
        } catch (e) {
          persistence = false;
          notice =
              'Saved chats could not be opened. The original archive will not be overwritten: $e';
        }
      }
      library.directory = directory;
      library.readCatalog(await rootBundle.loadString('assets/models.json'));
      if (cachedCatalog != null) {
        try { library.readCatalog(cachedCatalog); }
        catch (_) { notice = 'Saved model catalog could not be read; using the bundled catalog.'; }
      }
      library.addListener(notifyListeners);
      library.onChanged = save;
      if (model != null) library.remember(model!);
      conversationsReady = true;
      notifyListeners();
      if (manualStartup) {
        // Do not even enumerate devices: registry construction can enter the GPU driver.
        devices = [
          {'id': 'cpu', 'name': 'CPU', 'backend': 'CPU'},
          {
            'id': 'vulkan',
            'name': 'Vulkan (experimental)',
            'backend': 'Vulkan',
          },
        ];
        if (device != 'cpu' && device != 'vulkan') device = 'cpu';
        if (automatic) {
          context = profile.number('minimumContext');
          reply = profile.defaultReply(context);
          automatic = false;
        }
        initialized = true;
        loading = false;
        engineLabel = 'Model not loaded';
        if (persistence) notice = 'Choose your settings, then load the model. CPU with a small context is recommended on Android.';
        notifyListeners();
        return;
      }
      final events = await engine.command({'op': 'devices'});
      devices =
          (events.firstWhere((e) => e['type'] == 'devices')['devices'] as List)
              .map((e) => Json.from(e))
              .toList();
      initialized = true;
      loading = false;
      if (model == null ||
          !await File(model!['path']).exists() ||
          model!['bundled'] == true) {
        await useBundled();
      } else {
        await load();
      }
    } catch (e) {
      notice = '$e';
      loading = false;
      initialized = true;
      notifyListeners();
    }
  }

  Future<void> useBundled({bool loadModel = true}) async {
    if (busy) return;
    loading = true;
    notifyListeners();
    try {
      final path = await bundledModelPath();
      final file = File(path);
      if (!await file.exists() || await file.length() == 0) {
        loading = false;
        ready = false;
        notice = 'This package has no bundled model. Import a Mimir GGUF in Model and settings.';
        notifyListeners();
        return;
      }
      final id = (await sha256.bind(file.openRead()).first).toString();
      final previous = model;
      if (previous?['id'] != id) {
        profile = ModelProfile(
          Json.from(
            jsonDecode(await rootBundle.loadString('assets/profile.json')),
          ),
        );
        if (!manualStartup) automatic = true;
      }
      model = {
        'id': id,
        'name': 'DFM Mimir v1 Q4_K_M',
        'path': path,
        'bytes': await file.length(),
        'repo': 'danish-foundation-models/DFM-Mimir',
        'bundled': true,
        'profile': profile.data,
      };
      library.remember(model!);
      loading = false;
      if (loadModel) {
        await load();
      } else {
        ready = false;
        await save();
        notifyListeners();
      }
    } catch (e) {
      loading = false;
      notice = 'Could not open bundled model: $e';
      notifyListeners();
    }
  }

  Future<void> importModel(String source) async {
    if (busy) return;
    loading = true;
    notifyListeners();
    try {
      final file = File(source);
      final id = (await sha256.bind(file.openRead()).first).toString();
      final target = p.join(directory!.path, 'models', '$id.gguf');
      await Directory(p.dirname(target)).create(recursive: true);
      if (!await File(target).exists()) {
        final temp = '$target.importing';
        await file.copy(temp);
        await File(temp).rename(target);
      }
      profile = ModelProfile(
        Json.from(
          jsonDecode(await rootBundle.loadString('assets/profile.json')),
        ),
      );
      model = {
        'id': id,
        'name': p.basename(source),
        'bytes': await file.length(),
        'path': target,
        'bundled': false,
        'profile': profile.data,
      };
      library.remember(model!);
      automatic = !manualStartup;
      loading = false;
      if (manualStartup) {
        context = profile.number('minimumContext');
        reply = profile.defaultReply(context);
        ready = false;
        await save();
        notifyListeners();
      } else {
        await load();
      }
    } catch (e) {
      loading = false;
      notice = 'Model import failed: $e';
      notifyListeners();
    }
  }

  Future<void> selectModel(Json entry) async {
    if (busy) return;
    if (!await File(entry['path']).exists()) {
      setNotice('Model file is missing. Download or import it again.');
      return;
    }
    if (busy) return;
    model = Json.from(entry);
    profile = ModelProfile(Json.from(entry['profile']));
    automatic = !manualStartup && entry['source'] != 'hf-discovery';
    ready = false;
    context = profile.number('minimumContext');
    reply = profile.defaultReply(context);
    loading = true;
    notifyListeners();
    await save();
    loading = false;
    if (!manualStartup) await load();
    notifyListeners();
  }

  Future<void> deleteModel(Json entry) async {
    if (busy || entry['bundled'] == true || entry['id'] == model?['id'] ||
        entry['id'] == library.downloading) {
      return;
    }
    loading = true;
    notifyListeners();
    try {
      final file = File(entry['path']);
      // Only delete app-owned files, never an arbitrary imported source path.
      final owned = p.join(directory!.path, 'models', "${entry['id']}.gguf");
      if (p.equals(file.path, owned) && await file.exists()) await file.delete();
      library.installed.removeWhere((m) => m['id'] == entry['id']);
      await save();
      notifyListeners();
    } catch (e) {
      setNotice('Could not remove model: $e');
    } finally {
      loading = false;
      notifyListeners();
    }
  }

  Future<void> importProfile(String path) async {
    if (busy || model == null) return;
    try {
      profile = ModelProfile(
        Json.from(jsonDecode(await File(path).readAsString())),
      );
      model!['profile'] = profile.data;
      automatic = !manualStartup;
      if (manualStartup) {
        context = profile.number('minimumContext');
        reply = profile.defaultReply(context);
        ready = false;
        await save();
        notifyListeners();
      } else {
        await load();
      }
    } catch (e) {
      notice = 'Profile import failed: $e';
      notifyListeners();
    }
  }

  Future<void> startModel() async {
    if (busy) return;
    if (model == null || model!['bundled'] == true) {
      await useBundled();
    } else {
      await load();
    }
  }

  Future<void> load() async {
    if (manualStartup && _sessionDevice != null && _sessionDevice != device) {
      ready = false;
      notice = 'Backend saved. Force-stop DFM Mimir in Android app settings and reopen it before loading this backend.';
      await save();
      notifyListeners();
      return;
    }
    if (model == null) return;
    backendFallbackReasons = [];
    actualBackend = '';
    engineLabel = 'Loading model…';
    loading = true;
    ready = false;
    used = null;
    _countRevision++;
    notifyListeners();
    try {
      if (manualStartup) {
        // Persist choices before entering a driver that might hang or terminate the process.
        await save();
        _sessionDevice = device;
      }
      final events = await engine.command({
        'op': 'load',
        'path': model!['path'],
        'profile': profile.data,
        'modelBytes': await File(model!['path']).length(),
        'context': automatic ? 0 : context,
        'device': device,
        'mixedLM': mixedLM,
      });
      final loaded = events.firstWhere((e) => e['type'] == 'loaded');
      backendFallbackReasons = List<String>.from(
        loaded['fallbackReasons'] ?? [],
      );
      actualBackend = loaded['backend'] ?? loaded['device'];
      context = loaded['context'];
      training = loaded['trainingContext'];
      engineLabel =
          'On-device · ${loaded['device']}${mixedLM ? ' · MixedLM' : ''}';
      if (automatic) reply = profile.defaultReply(context);
      ready = true;
      if (persistence) notice = null;
    } catch (e) {
      notice = 'Model load failed: $e';
    }
    loading = false;
    notifyListeners();
    await save();
    await refreshCount();
  }

  Future<void> setLimits(
    int c,
    int r, {
    bool auto = false,
    String? backend,
    bool reload = true,
  }) async {
    if (busy) return;
    final error = profile.limitsError(c, r);
    if (!auto && error != null) {
      notice = error;
      notifyListeners();
      return;
    }
    context = c;
    reply = r;
    automatic = auto;
    if (backend != null) device = backend;
    if (manualStartup && (!ready || !reload)) {
      ready = false;
      await save();
      notifyListeners();
    } else {
      await load();
    }
  }

  Future<void> setMixedLM(bool enabled) async {
    if (busy || model == null || mixedLM == enabled) return;
    mixedLM = enabled;
    lastReusedTokens = 0;
    if (manualStartup && !ready) {
      await save();
      notifyListeners();
      return;
    }
    await load(); // A new context separates exact and approximate KV state.
  }

  void newChat() {
    if (!canCreateChat) return;
    final c = Conversation(modelID: model?['id']);
    chats.insert(0, c);
    selected = c.id;
    draft = '';
    streaming = '';
    notifyListeners();
    save();
    refreshCount();
  }

  void select(String id) {
    if (busy) return;
    selected = id;
    draft = '';
    streaming = '';
    notifyListeners();
    save();
    refreshCount();
  }

  void deleteActive() {
    if (busy) return;
    chats.removeWhere((c) => c.id == selected);
    selected = null;
    draft = '';
    notifyListeners();
    save();
    refreshCount();
  }

  void setCompaction({bool? enabled, bool? visible}) {
    if (busy) return;
    compact = enabled ?? compact;
    showSummary = visible ?? showSummary;
    notifyListeners();
    save();
    refreshCount();
  }

  Future<void> refreshCount() async {
    final revision = ++_countRevision;
    if (!ready || busy || !modelMatches) {
      used = null;
      notifyListeners();
      return;
    }
    try {
      final events = await engine.command({
        'op': 'count',
        'history': messages,
        'memory': active?.memory,
        'compact': compact,
      });
      if (revision == _countRevision && !busy) {
        used = events.firstWhere((e) => e['type'] == 'count')['tokens'];
      }
    } catch (_) {
      if (revision == _countRevision) used = null;
    }
    notifyListeners();
  }

  Future<void> send() async {
    if (!canSend) return;
    final prompt = draft.trim();
    if (active == null) newChat();
    final c = active!;
    if (c.messages.isEmpty) {
      c.title = String.fromCharCodes(prompt.runes.take(48));
      c.modelID = model?['id'];
    }
    c.updated = DateTime.now();
    chats.remove(c);
    chats.insert(0, c);
    draft = '';
    pending = prompt;
    streaming = '';
    preview = null;
    generating = true;
    compacting = false;
    notice = null;
    _countRevision++;
    notifyListeners();
    await save();
    try {
      final events = await engine.command(
        {
          'op': 'reply',
          'conversation': c.id,
          'history': c.messages,
          'memory': c.memory,
          'compact': compact,
          'prompt': prompt,
          'budget': reply,
        },
        onEvent: (e) {
          switch (e['type']) {
            case 'compacting':
              compacting = true;
            case 'summary':
              preview = {
                'summary': e['text'],
                'covered': e['covered'],
                'position': c.messages.length,
              };
            case 'promptSummary':
              preview = {
                'summary': e['text'],
                'covered': 0,
                'position': c.messages.length,
                'prompt': true,
              };
            case 'prepared':
              compacting = false;
              used = e['tokens'];
            case 'token':
              streaming += e['text'] as String;
          }
          notifyListeners();
        },
      );
      final result = events.firstWhere((e) => e['type'] == 'reply');
      lastReusedTokens = result['reusedPrefixTokens'] ?? 0;
      if (result['cancelled'] == true) {
        draft = prompt;
        notice = 'Reply stopped. Your message is back in the composer.';
      } else {
        if (result['memory'] != null) {
          final m = Json.from(result['memory']);
          final unchanged =
              m['summary'] == (c.memory?['summary']) &&
              m['covered'] == (c.memory?['covered']);
          m['position'] = unchanged
              ? (c.memory?['position'])
              : c.messages.length;
          c.memory = m;
        }
        c.messages.addAll([
          {
            'role': 'user',
            'content': prompt,
            if (result['compactedPrompt'] != null)
              'compactedContent': result['compactedPrompt'],
          },
          {'role': 'assistant', 'content': result['text']},
        ]);
        c.updated = DateTime.now();
        if (result['compactedPrompt'] != null) {
          notice = 'Your prompt was shortened to fit the context. The original is preserved; summaries may omit details.';
        }
        if (result['limited'] == true) {
          notice = [
            ?notice,
            'Reply reached the $reply-token limit. Increase the reply budget in settings.',
          ].join(' ');
        }
      }
    } catch (e) {
      draft = prompt;
      notice = '$e';
    } finally {
      generating = false;
      compacting = false;
      pending = null;
      streaming = '';
      preview = null;
      notifyListeners();
      await save();
      await refreshCount();
    }
  }

  void stop() {
    if (generating) engine.cancel();
  }

  Future<void> save() {
    if (!persistence || directory == null) return Future.value();
    final installedIndex = library.installed.indexWhere((m) => m['id'] == model?['id']);
    if (installedIndex >= 0) library.installed[installedIndex] = Json.from(model!);
    final data = jsonEncode({
      'version': 1,
      'chats': chats.map((c) => c.toJson()).toList(),
      'selected': selected,
      'model': model,
      'onlineFeedback': onlineFeedback,
      'modelNetwork': library.online,
      'userModelRepositories': library.userRepositories,
      'modelCatalog': {'version': 1, 'models': library.catalog.map((a) => a.data).toList()},
      'installedModels': library.installed,
      'discoveredModels': library.discovered,
      'unavailableModels': library.unavailable,
      'compact': compact,
      'mixedLM': mixedLM,
      'showSummary': showSummary,
      'automatic': automatic,
      'context': context,
      'reply': reply,
      'device': device,
    });
    _saving = _saving.then((_) async {
      try {
        final file = File(p.join(directory!.path, 'conversations.json'));
        final temp = File('${file.path}.tmp');
        await temp.writeAsString(data, flush: true);
        await temp.rename(file.path);
      } catch (e) {
        notice = 'Could not save chats: $e';
        notifyListeners();
      }
    });
    return _saving;
  }

  Future<void> shutdown() async {
    if (closing) return;
    stop();
    closing = true;
    notifyListeners();
    await setApiEnabled(false);
    await library.close();
    await engine.close();
    await _saving;
  }
}
