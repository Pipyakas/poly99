package com.pipyakas.poly99

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL

class GameCache(private val context: Context) {

    val baseUrl: String = BuildConfig.POLY99_URL.trimEnd('/')

    private val root = File(context.filesDir, "poly99")
    private val wwwDir = File(root, "www")
    private val stagingDir = File(root, "staging")
    private val prefs = context.getSharedPreferences("poly99", Context.MODE_PRIVATE)

    private val assets = listOf("index.html", "index.js", "index.wasm", "index.data")

    val cachedVersion: String
        get() = prefs.getString(KEY_VERSION, "") ?: ""

    fun hasCache(): Boolean = wwwDir.listFiles()?.isNotEmpty() == true

    fun cachedBytes(path: String): ByteArray? {
        val name = path.removePrefix("/").ifEmpty { "index.html" }
        val file = File(wwwDir, name)
        return if (file.exists()) file.readBytes() else null
    }

    fun fetchRemoteVersion(): String? {
        var conn: HttpURLConnection? = null
        return try {
            conn = URL("$baseUrl/version.json").openConnection() as HttpURLConnection
            conn.connectTimeout = 8000
            conn.readTimeout = 8000
            if (conn.responseCode == 200) {
                val body = conn.inputStream.bufferedReader().use { it.readText() }
                JSONObject(body).optString("version").takeIf { it.isNotBlank() }
            } else {
                null
            }
        } catch (e: Exception) {
            null
        } finally {
            conn?.disconnect()
        }
    }

    fun downloadToStaging(): Boolean {
        deleteRecursively(stagingDir)
        if (!stagingDir.mkdirs()) return false
        for (asset in assets) {
            var conn: HttpURLConnection? = null
            try {
                conn = URL("$baseUrl/$asset").openConnection() as HttpURLConnection
                conn.connectTimeout = 15000
                conn.readTimeout = 30000
                if (conn.responseCode != 200) return false
                conn.inputStream.use { input ->
                    FileOutputStream(File(stagingDir, asset)).use { output -> input.copyTo(output) }
                }
            } catch (e: Exception) {
                return false
            } finally {
                conn?.disconnect()
            }
        }
        return true
    }

    fun activateStaging(version: String) {
        deleteRecursively(wwwDir)
        if (stagingDir.exists()) stagingDir.renameTo(wwwDir)
        prefs.edit().putString(KEY_VERSION, version).apply()
    }

    private fun deleteRecursively(file: File) {
        file.listFiles()?.forEach { if (it.isDirectory) deleteRecursively(it) else it.delete() }
        file.delete()
    }

    private companion object {
        const val KEY_VERSION = "cached_version"
    }
}
