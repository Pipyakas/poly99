#include "metrics.h"

#include "raylib.h"

#include <cstdio>

#if defined(__EMSCRIPTEN__)
#include <emscripten.h>
#endif

#if !defined(__EMSCRIPTEN__)
#include <unistd.h>
#endif

namespace {

struct Metrics {
    bool enabled = true;
    int fps = 0;
    float frameMs = 0.0f;
    float updateMs = 0.0f;
    float drawMs = 0.0f;
    float gpuMs = -1.0f;
    long long ramUsed = 0;
    long long ramTotal = 0;
    long long vramBytes = 0;
    char gpuName[96] = "";
    double updateStart = 0.0;
    double drawStart = 0.0;
    double lastRamSample = 0.0;
};

Metrics m;

double now() { return GetTime(); }

#if defined(__EMSCRIPTEN__)
void gpuInit() {
    EM_ASM({
        if (window.__poly99GL) return;
        var gl = Module.ctx || (typeof GL !== 'undefined' && GL.currentContext && GL.currentContext.GLctx);
        if (!gl) return;
        gl.getError();
        var webgl2 = !!gl.createQuery;
        var ext = gl.getExtension(webgl2 ? 'EXT_disjoint_timer_query_webgl2' : 'EXT_disjoint_timer_query');
        if (!ext) return;
        var q = webgl2 ? gl.createQuery() : ext.createQueryEXT();
        if (!q) return;
        var pname = ext.TIME_ELAPSED_EXT;
        if (webgl2) {
            gl.beginQuery(pname, q);
            gl.endQuery(pname);
            gl.getQueryParameter(q, ext.QUERY_RESULT_AVAILABLE_EXT);
        } else {
            ext.beginQueryEXT(pname, q);
            ext.endQueryEXT(pname);
            ext.getQueryParameterEXT(q, ext.QUERY_RESULT_AVAILABLE_EXT);
        }
        if (gl.getError() !== gl.NO_ERROR) return;
        window.__poly99GL = gl;
        window.__poly99EXT = ext;
        window.__poly99WEBGL2 = webgl2 ? 1 : 0;
        window.__poly99Q = q;
    });
}

void gpuBegin() {
    EM_ASM({
        var gl = window.__poly99GL;
        var ext = window.__poly99EXT;
        if (!gl || !ext || window.__poly99Q) return;
        if (window.__poly99WEBGL2) {
            window.__poly99Q = gl.createQuery();
            gl.beginQuery(ext.TIME_ELAPSED_EXT, window.__poly99Q);
        } else {
            window.__poly99Q = ext.createQueryEXT();
            ext.beginQueryEXT(ext.TIME_ELAPSED_EXT, window.__poly99Q);
        }
    });
}

void gpuEnd() {
    EM_ASM({
        var gl = window.__poly99GL;
        var ext = window.__poly99EXT;
        if (!gl || !ext || !window.__poly99Q) return;
        if (window.__poly99WEBGL2) gl.endQuery(ext.TIME_ELAPSED_EXT);
        else ext.endQueryEXT(ext.TIME_ELAPSED_EXT);
    });
}

double gpuReadMs() {
    double r = EM_ASM_DOUBLE({
        var gl = window.__poly99GL;
        var ext = window.__poly99EXT;
        if (!gl || !ext || !window.__poly99Q) return -1;
        if (window.__poly99WEBGL2) {
            if (gl.getQueryParameter(window.__poly99Q, ext.QUERY_RESULT_AVAILABLE_EXT)) {
                var ns = gl.getQueryParameter(window.__poly99Q, ext.QUERY_RESULT_EXT);
                gl.deleteQuery(window.__poly99Q);
                window.__poly99Q = null;
                return ns / 1000000.0;
            }
        } else {
            if (ext.getQueryParameterEXT(window.__poly99Q, ext.QUERY_RESULT_AVAILABLE_EXT)) {
                var ns = ext.getQueryParameterEXT(window.__poly99Q, ext.QUERY_RESULT_EXT);
                ext.deleteQueryEXT(window.__poly99Q);
                window.__poly99Q = null;
                return ns / 1000000.0;
            }
        }
        return -1;
    });
    return r;
}

void getGpuName(char* out, int size) {
    EM_ASM({
        var gl = Module.ctx || (typeof GL !== 'undefined' && GL.currentContext && GL.currentContext.GLctx);
        var name = 'n/a';
        if (gl) {
            var dbg = gl.getExtension('WEBGL_debug_renderer_info');
            if (dbg) name = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || 'n/a';
        }
        stringToUTF8(name, $0, $1);
    }, out, size);
}

void getRam(long long& used, long long& total) {
    used = (long long)EM_ASM_INT({ return (typeof performance !== 'undefined' && performance.memory) ? performance.memory.usedJSHeapSize : 0; });
    total = (long long)EM_ASM_INT({ return HEAPU8.length; });
}
#else
void gpuInit() {}
void gpuBegin() {}
void gpuEnd() {}
double gpuReadMs() { return -1; }

void getGpuName(char* out, int size) {
    snprintf(out, (size_t)size, "desktop");
}

void getRam(long long& used, long long& total) {
    used = 0;
    total = 0;
    FILE* f = fopen("/proc/self/statm", "r");
    if (f) {
        long size = 0;
        long rss = 0;
        if (fscanf(f, "%ld %ld", &size, &rss) == 2) {
            long page = sysconf(_SC_PAGESIZE);
            used = (long long)rss * page;
            total = (long long)size * page;
        }
        fclose(f);
    }
}
#endif

void formatBytes(char* out, int size, long long bytes) {
    if (bytes >= 1024 * 1024) snprintf(out, (size_t)size, "%.1f MB", bytes / (1024.0 * 1024.0));
    else if (bytes >= 1024) snprintf(out, (size_t)size, "%.0f KB", bytes / 1024.0);
    else snprintf(out, (size_t)size, "%lld B", bytes);
}

} // namespace

void metricsInit() {
    gpuInit();
    getGpuName(m.gpuName, sizeof(m.gpuName));
    Texture2D font = GetFontDefault().texture;
    if (font.id != 0) metricsAddTextureBytes(font.width * font.height * 4);
    getRam(m.ramUsed, m.ramTotal);
}

void metricsToggle() { m.enabled = !m.enabled; }
bool metricsEnabled() { return m.enabled; }

void metricsAddTextureBytes(int bytes) { m.vramBytes += bytes; }

void metricsBeginFrame() {
    m.fps = GetFPS();
    m.frameMs = GetFrameTime() * 1000.0f;
    double gpu = gpuReadMs();
    if (gpu >= 0.0) m.gpuMs = (float)gpu;
    m.updateStart = now();
    gpuBegin();
}

void metricsEndUpdate() {
    m.updateMs = (float)((now() - m.updateStart) * 1000.0);
    m.drawStart = now();
}

void metricsEndDraw() {
    m.drawMs = (float)((now() - m.drawStart) * 1000.0);
    gpuEnd();
}

void drawMetrics() {
    if (!m.enabled) return;

    double t = now();
    if (t - m.lastRamSample > 0.5) {
        getRam(m.ramUsed, m.ramTotal);
        m.lastRamSample = t;
    }

    const int fs = 16;
    const int lines = 5;
    float x = 12.0f;
    float y = (float)GetScreenHeight() - 12.0f - (float)(lines * fs);

    DrawRectangle((int)x - 6, (int)y - 6, 320, lines * fs + 12, (Color){ 0, 0, 0, 150 });

    char buf[160];
    char tmp[32];

    snprintf(buf, sizeof(buf), "FPS %d", m.fps);
    DrawText(buf, (int)x, (int)y + 0 * fs, fs, (Color){ 0, 255, 255, 255 });
    snprintf(buf, sizeof(buf), "CPU %.1f ms  (upd %.2f / drw %.2f)", m.frameMs, m.updateMs, m.drawMs);
    DrawText(buf, (int)x, (int)y + 1 * fs, fs, RAYWHITE);

    if (m.gpuMs >= 0.0f) snprintf(buf, sizeof(buf), "GPU %.2f ms", m.gpuMs);
    else snprintf(buf, sizeof(buf), "GPU n/a");
    DrawText(buf, (int)x, (int)y + 2 * fs, fs, RAYWHITE);

    formatBytes(tmp, sizeof(tmp), m.ramUsed);
    char total[32];
    formatBytes(total, sizeof(total), m.ramTotal);
    snprintf(buf, sizeof(buf), "RAM %s / %s", tmp, total);
    DrawText(buf, (int)x, (int)y + 3 * fs, fs, RAYWHITE);

    formatBytes(tmp, sizeof(tmp), m.vramBytes);
    snprintf(buf, sizeof(buf), "VRAM %s  (%s)", tmp, m.gpuName);
    DrawText(buf, (int)x, (int)y + 4 * fs, fs, RAYWHITE);
}
