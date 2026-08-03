package com.pipyakas.poly99

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.pm.ActivityInfo
import android.os.Bundle
import android.view.Gravity
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.FrameLayout
import java.io.ByteArrayInputStream

class MainActivity : Activity() {

    private lateinit var webView: WebView
    private lateinit var cache: GameCache
    private var promptShown = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        cache = GameCache(this)

        applyOrientation()

        webView = WebView(this)
        webView.setBackgroundColor(0xFF000000.toInt())

        val settingsButton = Button(this).apply {
            text = "\u2699"
            textSize = 18f
            alpha = 0.6f
            setOnClickListener { showSettings() }
        }

        val root = FrameLayout(this)
        root.addView(
            webView,
            FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
        )
        val buttonParams = FrameLayout.LayoutParams(
            ViewGroup.LayoutParams.WRAP_CONTENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        buttonParams.gravity = Gravity.END or Gravity.BOTTOM
        buttonParams.setMargins(0, 0, dp(16), dp(16))
        root.addView(settingsButton, buttonParams)

        setContentView(root)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)

        setupWebView()
        webView.loadUrl("${cache.baseUrl}/index.html")
        checkForUpdateInBackground()
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun setupWebView() {
        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            mediaPlaybackRequiresUserGesture = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            cacheMode = WebSettings.LOAD_DEFAULT
        }
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView,
                request: WebResourceRequest
            ): WebResourceResponse? {
                val path = request.url.path ?: return null
                val bytes = cache.cachedBytes(path) ?: return null
                val (mime, encoding) = when {
                    path.endsWith(".wasm") -> "application/wasm" to null
                    path.endsWith(".js") -> "application/javascript" to "UTF-8"
                    path.endsWith(".data") -> "application/octet-stream" to null
                    path.endsWith(".png") -> "image/png" to null
                    else -> "text/html" to "UTF-8"
                }
                return WebResourceResponse(mime, encoding, ByteArrayInputStream(bytes))
            }
        }
        webView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN
    }

    private fun checkForUpdateInBackground() {
        Thread {
            val remote = cache.fetchRemoteVersion() ?: return@Thread
            if (!cache.hasCache() || remote != cache.cachedVersion) {
                if (cache.downloadToStaging()) {
                    if (cache.hasCache()) {
                        runOnUiThread { promptUpdate(remote) }
                    } else {
                        cache.activateStaging(remote)
                    }
                }
            }
        }.start()
    }

    private fun promptUpdate(newVersion: String) {
        if (promptShown || isFinishing) return
        promptShown = true
        AlertDialog.Builder(this)
            .setTitle("Update available")
            .setMessage("A newer version (v$newVersion) is available. Reload to update?")
            .setPositiveButton("Update now") { _, _ ->
                cache.activateStaging(newVersion)
                webView.reload()
            }
            .setNegativeButton("Later", null)
            .setCancelable(false)
            .show()
    }

    private fun showSettings() {
        val options = arrayOf("Landscape", "Portrait", "Auto")
        val current = when (orientationPref()) {
            "portrait" -> 1
            "auto" -> 2
            else -> 0
        }
        AlertDialog.Builder(this)
            .setTitle("Settings")
            .setSingleChoiceItems(options, current) { dialog, which ->
                when (which) {
                    0 -> setOrientation("landscape")
                    1 -> setOrientation("portrait")
                    2 -> setOrientation("auto")
                }
                dialog.dismiss()
            }
            .setNegativeButton("Close", null)
            .show()
    }

    private fun orientationPref(): String =
        getSharedPreferences("poly99", MODE_PRIVATE)
            .getString("orientation", "landscape") ?: "landscape"

    private fun setOrientation(value: String) {
        getSharedPreferences("poly99", MODE_PRIVATE).edit().putString("orientation", value).apply()
        applyOrientation()
    }

    private fun applyOrientation() {
        requestedOrientation = when (orientationPref()) {
            "portrait" -> ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            "auto" -> ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED
            else -> ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
        }
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    @Deprecated("Deprecated in Java")
    override fun onBackPressed() {
        if (webView.canGoBack()) webView.goBack() else super.onBackPressed()
    }

    override fun onDestroy() {
        webView.destroy()
        super.onDestroy()
    }
}
