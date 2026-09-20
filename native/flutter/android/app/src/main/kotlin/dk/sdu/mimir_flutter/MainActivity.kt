package dk.sdu.mimir_flutter

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import kotlin.concurrent.thread

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "dk.sdu.mimir/assets")
            .setMethodCallHandler { call, result ->
                if (call.method != "bundledModelPath") {
                    result.notImplemented()
                } else {
                    thread(name = "mimir-model-extraction") {
                        try {
                            val path = extractModel()
                            runOnUiThread { result.success(path) }
                        } catch (e: Exception) {
                            runOnUiThread { result.error("model_asset", e.message, null) }
                        }
                    }
                }
            }
    }

    // No backup: model weights are reproducible resources, not user data.
    @Synchronized
    private fun extractModel(): String {
        val asset = "flutter_assets/assets/model.gguf"
        val target = File(noBackupFilesDir, "bundled-model.gguf")
        val stamp = File(noBackupFilesDir, "bundled-model.version")
        val update = packageManager.getPackageInfo(packageName, 0).lastUpdateTime.toString()
        val size = assets.openFd(asset).use { it.length }
        if (target.length() == size && stamp.exists() && stamp.readText() == update) {
            return target.absolutePath
        }
        val partial = File(noBackupFilesDir, "bundled-model.partial")
        try {
            assets.open(asset).use { input ->
                partial.outputStream().use { output ->
                    input.copyTo(output, 1024 * 1024)
                    output.fd.sync()
                }
            }
            check(partial.length() == size) { "Incomplete bundled model" }
            check(partial.renameTo(target)) { "Could not install bundled model" }
            stamp.writeText(update)
        } finally {
            partial.delete()
        }
        return target.absolutePath
    }
}
