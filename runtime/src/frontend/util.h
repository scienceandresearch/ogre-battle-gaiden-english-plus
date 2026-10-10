/*
 * Frontend utilities: strings, paths, files, console output, message boxes,
 * timing. Windows only.
 */
#ifndef ZEN_UTIL_H
#define ZEN_UTIL_H

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <stddef.h>
#include <stdint.h>

#define ZEN_TITLE L"Ogre Battle Gaiden: Prince of Zenobia (English)"

/* 0 = never show modal dialogs (selftest, --exit-after, --write-patched):
   questions get their default answer and messages go to stderr. */
extern int g_zen_interactive;

/* ---- strings (returned strings are malloc'd; release with free()) ---- */
wchar_t *zen_wcsdup(const wchar_t *s);
char    *zen_to_utf8(const wchar_t *s);
wchar_t *zen_from_utf8(const char *s);
/* A narrow path the core's fopen() can open (UTF-8 when the process code
   page is UTF-8, which the manifest requests; otherwise the ANSI code page
   or a short 8.3 path). NULL if no usable form exists. */
char    *zen_core_path(const wchar_t *path);

/* ---- paths ---- */
const wchar_t *zen_exe_dir(void);                      /* no trailing separator */
wchar_t *zen_path_join(const wchar_t *dir, const wchar_t *name);
const wchar_t *zen_path_name(const wchar_t *path);     /* file name part */
wchar_t *zen_path_stem(const wchar_t *path);           /* name without extension */
wchar_t *zen_full_path(const wchar_t *path);
int      zen_file_exists(const wchar_t *path);
int      zen_make_dir(const wchar_t *path);            /* 1 if the directory exists afterwards */

/* ---- files ---- */
enum { ZEN_FILE_OK = 0, ZEN_FILE_MISSING, ZEN_FILE_TOO_BIG, ZEN_FILE_IOERR, ZEN_FILE_NOMEM };
int  zen_read_file(const wchar_t *path, uint8_t **data, size_t *size, size_t max_size);
/* Writes to "<path>.tmp" and renames it over path. */
int  zen_write_file_atomic(const wchar_t *path, const void *data, size_t size);
int  zen_replace_file(const wchar_t *src, const wchar_t *dst);
const char *zen_file_error(int err);

/* ---- console and messages ---- */
/* Makes stdout/stderr usable in this GUI-subsystem program: keeps inherited
   pipes/files, otherwise attaches to the parent console (or allocates one
   when alloc_if_missing). Returns 1 if stderr is usable. */
int  zen_console_init(int alloc_if_missing);
void zen_logf(const char *fmt, ...);
/* MessageBoxW with the player's title. When not interactive, prints the
   text to stderr and returns noninteractive_answer. */
int  zen_message(HWND owner, UINT flags, int noninteractive_answer, const wchar_t *fmt, ...);

/* ---- time ---- */
int64_t zen_qpc(void);
int64_t zen_qpc_freq(void);
double  zen_seconds(void);   /* monotonic, since the first call */

#endif
