/*
 * Frontend utilities. See util.h.
 */
#include "util.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

int g_zen_interactive = 1;

/* ------------------------------------------------------------------ */
/* Strings                                                              */
/* ------------------------------------------------------------------ */

wchar_t *zen_wcsdup(const wchar_t *s)
{
    if (!s) return NULL;
    size_t n = wcslen(s) + 1;
    wchar_t *d = (wchar_t *)malloc(n * sizeof(wchar_t));
    if (d) memcpy(d, s, n * sizeof(wchar_t));
    return d;
}

char *zen_to_utf8(const wchar_t *s)
{
    if (!s) return NULL;
    int n = WideCharToMultiByte(CP_UTF8, 0, s, -1, NULL, 0, NULL, NULL);
    if (n <= 0) return NULL;
    char *d = (char *)malloc((size_t)n);
    if (!d) return NULL;
    WideCharToMultiByte(CP_UTF8, 0, s, -1, d, n, NULL, NULL);
    return d;
}

wchar_t *zen_from_utf8(const char *s)
{
    if (!s) return NULL;
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, NULL, 0);
    if (n <= 0) return NULL;
    wchar_t *d = (wchar_t *)malloc((size_t)n * sizeof(wchar_t));
    if (!d) return NULL;
    MultiByteToWideChar(CP_UTF8, 0, s, -1, d, n);
    return d;
}

/* Converts to the ANSI code page; NULL if any character cannot be represented. */
static char *to_acp_exact(const wchar_t *s)
{
    BOOL lossy = FALSE;
    int n = WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, s, -1, NULL, 0, NULL, &lossy);
    if (n <= 0 || lossy) return NULL;
    char *d = (char *)malloc((size_t)n);
    if (!d) return NULL;
    lossy = FALSE;
    WideCharToMultiByte(CP_ACP, WC_NO_BEST_FIT_CHARS, s, -1, d, n, NULL, &lossy);
    if (lossy) { free(d); return NULL; }
    return d;
}

static wchar_t *short_path(const wchar_t *path)
{
    DWORD n = GetShortPathNameW(path, NULL, 0);
    if (!n) return NULL;
    wchar_t *d = (wchar_t *)malloc((size_t)n * sizeof(wchar_t));
    if (!d) return NULL;
    DWORD r = GetShortPathNameW(path, d, n);
    if (!r || r >= n) { free(d); return NULL; }
    return d;
}

char *zen_core_path(const wchar_t *path)
{
    if (!path) return NULL;
    if (GetACP() == CP_UTF8) return zen_to_utf8(path);

    char *s = to_acp_exact(path);
    if (s) return s;

    /* Older Windows without the UTF-8 code page: try the 8.3 form of the
       whole path, then of its directory plus the (representable) name. */
    wchar_t *sp = short_path(path);
    if (sp) {
        s = to_acp_exact(sp);
        free(sp);
        if (s) return s;
    }
    const wchar_t *name = zen_path_name(path);
    if (name == path) return NULL;
    size_t dirlen = (size_t)(name - path);
    wchar_t *dir = (wchar_t *)malloc((dirlen + 1) * sizeof(wchar_t));
    if (!dir) return NULL;
    memcpy(dir, path, dirlen * sizeof(wchar_t));
    dir[dirlen] = 0;
    wchar_t *sdir = short_path(dir);
    free(dir);
    if (!sdir) return NULL;
    wchar_t *joined = zen_path_join(sdir, name);
    free(sdir);
    if (!joined) return NULL;
    s = to_acp_exact(joined);
    free(joined);
    return s;
}

/* ------------------------------------------------------------------ */
/* Paths                                                                */
/* ------------------------------------------------------------------ */

const wchar_t *zen_exe_dir(void)
{
    static wchar_t *dir;
    if (dir) return dir;
    DWORD cap = 260;
    for (;;) {
        wchar_t *buf = (wchar_t *)malloc(cap * sizeof(wchar_t));
        if (!buf) return L".";
        DWORD n = GetModuleFileNameW(NULL, buf, cap);
        if (n == 0) { free(buf); return L"."; }
        if (n < cap) {
            wchar_t *name = (wchar_t *)zen_path_name(buf);
            if (name > buf) name[-1] = 0;
            else wcscpy(buf, L".");
            dir = buf;
            return dir;
        }
        free(buf);
        if (cap >= 32768) return L".";
        cap *= 2;
    }
}

wchar_t *zen_path_join(const wchar_t *dir, const wchar_t *name)
{
    size_t a = wcslen(dir), b = wcslen(name);
    int sep = a > 0 && dir[a - 1] != L'\\' && dir[a - 1] != L'/';
    wchar_t *d = (wchar_t *)malloc((a + b + 2) * sizeof(wchar_t));
    if (!d) return NULL;
    memcpy(d, dir, a * sizeof(wchar_t));
    if (sep) d[a++] = L'\\';
    memcpy(d + a, name, (b + 1) * sizeof(wchar_t));
    return d;
}

const wchar_t *zen_path_name(const wchar_t *path)
{
    const wchar_t *name = path;
    for (const wchar_t *p = path; *p; p++)
        if (*p == L'\\' || *p == L'/' || *p == L':') name = p + 1;
    return name;
}

wchar_t *zen_path_stem(const wchar_t *path)
{
    wchar_t *d = zen_wcsdup(zen_path_name(path));
    if (!d) return NULL;
    wchar_t *dot = wcsrchr(d, L'.');
    if (dot && dot != d) *dot = 0;
    return d;
}

wchar_t *zen_full_path(const wchar_t *path)
{
    DWORD n = GetFullPathNameW(path, 0, NULL, NULL);
    if (!n) return zen_wcsdup(path);
    wchar_t *d = (wchar_t *)malloc((size_t)n * sizeof(wchar_t));
    if (!d) return NULL;
    DWORD r = GetFullPathNameW(path, n, d, NULL);
    if (!r || r >= n) { free(d); return zen_wcsdup(path); }
    return d;
}

int zen_file_exists(const wchar_t *path)
{
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY);
}

int zen_make_dir(const wchar_t *path)
{
    if (CreateDirectoryW(path, NULL)) return 1;
    DWORD a = GetFileAttributesW(path);
    return a != INVALID_FILE_ATTRIBUTES && (a & FILE_ATTRIBUTE_DIRECTORY);
}

/* ------------------------------------------------------------------ */
/* Files                                                                */
/* ------------------------------------------------------------------ */

int zen_read_file(const wchar_t *path, uint8_t **data, size_t *size, size_t max_size)
{
    *data = NULL;
    *size = 0;
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) {
        DWORD e = GetLastError();
        return (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) ? ZEN_FILE_MISSING : ZEN_FILE_IOERR;
    }
    LARGE_INTEGER li;
    if (!GetFileSizeEx(h, &li) || li.QuadPart < 0) { CloseHandle(h); return ZEN_FILE_IOERR; }
    if ((uint64_t)li.QuadPart > (uint64_t)max_size) { CloseHandle(h); return ZEN_FILE_TOO_BIG; }
    size_t n = (size_t)li.QuadPart;
    uint8_t *buf = (uint8_t *)malloc(n ? n : 1);
    if (!buf) { CloseHandle(h); return ZEN_FILE_NOMEM; }
    size_t got = 0;
    while (got < n) {
        DWORD chunk = (DWORD)((n - got) > (1u << 30) ? (1u << 30) : (n - got)), r = 0;
        if (!ReadFile(h, buf + got, chunk, &r, NULL) || r == 0) break;
        got += r;
    }
    CloseHandle(h);
    if (got != n) { free(buf); return ZEN_FILE_IOERR; }
    *data = buf;
    *size = n;
    return ZEN_FILE_OK;
}

int zen_replace_file(const wchar_t *src, const wchar_t *dst)
{
    return MoveFileExW(src, dst, MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH) ? 1 : 0;
}

int zen_write_file_atomic(const wchar_t *path, const void *data, size_t size)
{
    wchar_t *tmp = (wchar_t *)malloc((wcslen(path) + 5) * sizeof(wchar_t));
    if (!tmp) return ZEN_FILE_NOMEM;
    wcscpy(tmp, path);
    wcscat(tmp, L".tmp");
    HANDLE h = CreateFileW(tmp, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) { free(tmp); return ZEN_FILE_IOERR; }
    const uint8_t *p = (const uint8_t *)data;
    size_t done = 0;
    int ok = 1;
    while (done < size) {
        DWORD chunk = (DWORD)((size - done) > (1u << 30) ? (1u << 30) : (size - done)), w = 0;
        if (!WriteFile(h, p + done, chunk, &w, NULL) || w == 0) { ok = 0; break; }
        done += w;
    }
    if (ok && !FlushFileBuffers(h)) ok = 0;
    CloseHandle(h);
    if (ok) ok = zen_replace_file(tmp, path);
    if (!ok) DeleteFileW(tmp);
    free(tmp);
    return ok ? ZEN_FILE_OK : ZEN_FILE_IOERR;
}

const char *zen_file_error(int err)
{
    switch (err) {
    case ZEN_FILE_OK:      return "ok";
    case ZEN_FILE_MISSING: return "file not found";
    case ZEN_FILE_TOO_BIG: return "file too large";
    case ZEN_FILE_NOMEM:   return "out of memory";
    default:               return "read/write error";
    }
}

/* ------------------------------------------------------------------ */
/* Console and messages                                                 */
/* ------------------------------------------------------------------ */

static int handle_usable(DWORD which)
{
    HANDLE h = GetStdHandle(which);
    return h && h != INVALID_HANDLE_VALUE && GetFileType(h) != FILE_TYPE_UNKNOWN;
}

int zen_console_init(int alloc_if_missing)
{
    int out_ok = handle_usable(STD_OUTPUT_HANDLE);
    int err_ok = handle_usable(STD_ERROR_HANDLE);
    if (!out_ok || !err_ok) {
        if (AttachConsole(ATTACH_PARENT_PROCESS) || (alloc_if_missing && AllocConsole())) {
            FILE *f;
            if (!out_ok && freopen_s(&f, "CONOUT$", "w", stdout) == 0) out_ok = 1;
            if (!err_ok && freopen_s(&f, "CONOUT$", "w", stderr) == 0) err_ok = 1;
        }
    }
    if (err_ok) setvbuf(stderr, NULL, _IONBF, 0);
    return err_ok;
}

void zen_logf(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fflush(stderr);
}

int zen_message(HWND owner, UINT flags, int noninteractive_answer, const wchar_t *fmt, ...)
{
    wchar_t text[4096];
    va_list ap;
    va_start(ap, fmt);
    _vsnwprintf_s(text, sizeof(text) / sizeof(text[0]), _TRUNCATE, fmt, ap);
    va_end(ap);
    if (!g_zen_interactive) {
        char *u = zen_to_utf8(text);
        zen_logf("%s\n", u ? u : "(message)");
        free(u);
        return noninteractive_answer;
    }
    return MessageBoxW(owner, text, ZEN_TITLE, flags | MB_SETFOREGROUND);
}

/* ------------------------------------------------------------------ */
/* Time                                                                 */
/* ------------------------------------------------------------------ */

int64_t zen_qpc(void)
{
    LARGE_INTEGER li;
    QueryPerformanceCounter(&li);
    return li.QuadPart;
}

int64_t zen_qpc_freq(void)
{
    static int64_t f;
    if (!f) {
        LARGE_INTEGER li;
        QueryPerformanceFrequency(&li);
        f = li.QuadPart ? li.QuadPart : 1;
    }
    return f;
}

double zen_seconds(void)
{
    static int64_t t0;
    if (!t0) t0 = zen_qpc();
    return (double)(zen_qpc() - t0) / (double)zen_qpc_freq();
}
