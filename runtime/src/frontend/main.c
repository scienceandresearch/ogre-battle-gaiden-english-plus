/*
 * zenobia.exe: standalone Windows player for Ogre Battle Gaiden: Prince of
 * Zenobia (English). Entry point and command line.
 *
 *   zenobia [ROM] [--patch FILE] [--untranslated] [--console] [--log N]
 *           [--exit-after SECONDS] [--png FILE] [--png-scale N]
 *   zenobia ROM --write-patched OUT [--patch FILE]
 *   zenobia --selftest ROM [options, see selftest.c]
 *   zenobia --bps-apply SOURCE PATCH OUT
 *   zenobia --unzip ZIP OUT
 * ROM may be a .zip holding the game file (romload.h).
 */
#include "app.h"
#include "bps.h"
#include "sha1.h"
#include "zipread.h"

#include "core/ngp.h"

#include <shellapi.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const wchar_t k_usage[] =
    L"Usage: zenobia [ROM] [options]\n"
    L"  ROM                   .ngc/.ngp/.npc file, or a .zip holding it\n"
    L"                        (default: the last ROM, or a file dialog)\n"
    L"  --patch FILE          English patch (default: ogre_en.bps next to zenobia.exe,\n"
    L"                        else next to the ROM)\n"
    L"  --untranslated        accept the Japanese ROM without the patch\n"
    L"  --console             show log messages in a console\n"
    L"  --log N               core log level (0 = quiet)\n"
    L"  --exit-after SECONDS  run the window for SECONDS, then quit (smoke test)\n"
    L"  --png FILE            with --exit-after or --selftest: last frame as PNG\n"
    L"  --png-scale N         PNG scale factor (default 2, like ngp_harness)\n"
    L"  --write-patched OUT   write the patched ROM to OUT and exit\n"
    L"  --selftest ROM        headless run; also --frames N, --input \"F:BUTTONS:LEN;...\",\n"
    L"                        --save FLASHFILE, --load-state FILE, --load-state-at F FILE,\n"
    L"                        --save-state F FILE\n"
    L"  --no-flash-commands   ignore the game's flash commands (in-game saving then fails)\n"
    L"  --bps-apply SOURCE PATCH OUT   apply any BPS patch\n"
    L"  --unzip ZIP OUT       unpack the game file of a zip, chosen as for ROM\n";

/* Asks p->question after p->message (default button = p->default_yes). */
static int ask_yes(HWND owner, const RomPrep *p)
{
    UINT flags = MB_YESNO | MB_ICONWARNING | (p->default_yes ? MB_DEFBUTTON1 : MB_DEFBUTTON2);
    return zen_message(owner, flags, p->default_yes ? IDYES : IDNO, L"%ls\n\n%ls", p->message, p->question) == IDYES;
}

int app_prepare_rom(HWND owner, const wchar_t *rom_path, const wchar_t *patch,
                    int allow_untranslated, RomPrep *p)
{
    RomPrepStatus st = rom_prepare(rom_path, patch, p);
    switch (st) {
    case ROMPREP_READY:
        return 1;
    case ROMPREP_ERROR:
        zen_message(owner, MB_OK | MB_ICONERROR, IDOK, L"%ls", p->message);
        return 0;
    case ROMPREP_ASK_UNTRANSLATED:
        if (allow_untranslated) {
            if (!g_zen_interactive) zen_logf("note: running the Japanese ROM untranslated (--untranslated)\n");
            rom_prep_accept_as_is(p);
            return 1;
        }
        if (!g_zen_interactive) {
            zen_message(owner, 0, IDNO, L"%ls\n(Not run. Pass --untranslated to run it anyway.)", p->message);
            return 0;
        }
        if (ask_yes(owner, p)) {
            rom_prep_accept_as_is(p);
            return 1;
        }
        return 0;
    case ROMPREP_ASK_UNKNOWN:
    default:
        if (!g_zen_interactive) {
            /* headless runs (agents, tests) run modified ROMs without asking */
            char hex[41];
            sha1_hex(p->file_sha1, hex);
            char *u = zen_to_utf8(p->rom_path);
            char *z = p->zip.name ? zen_to_utf8(p->zip.name) : NULL;
            char *w = zen_to_utf8(p->why);
            zen_logf("warning: %s%s%s%s is not a ROM the patch knows (sha1 %s, crc32 %08x); running it as is\n"
                     "  (%s)\n", u ? u : "?", z ? " (file in the zip: " : "", z ? z : "", z ? ")" : "",
                     hex, (unsigned)p->file_crc, w ? w : "");
            free(u);
            free(z);
            free(w);
            rom_prep_accept_as_is(p);
            return 1;
        }
        if (ask_yes(owner, p)) {
            rom_prep_accept_as_is(p);
            return 1;
        }
        return 0;
    }
}

static int run_write_patched(const Options *o)
{
    if (!o->rom) {
        zen_logf("--write-patched: no ROM given\n");
        return EXIT_USAGE;
    }
    /* No questions here: only the original ROM with a usable patch (or the
       English ROM itself) gives a translated image to write. */
    RomPrep p;
    RomPrepStatus st = rom_prepare(o->rom, o->patch, &p);
    if (st != ROMPREP_READY) {
        char *u = zen_to_utf8(p.message);
        zen_logf("%s\n--write-patched: nothing written\n", u ? u : "cannot use the ROM");
        free(u);
        int code = p.file ? EXIT_ROM_REFUSED : EXIT_ROM_UNREADABLE;
        rom_prep_free(&p);
        return code;
    }
    int ok = rom_write_image(&p, o->write_patched);
    char *u = zen_to_utf8(o->write_patched);
    zen_logf(ok ? "wrote %s (%s)\n" : "cannot write %s\n", u ? u : "?",
             p.patched ? "patched" : "already English");
    free(u);
    rom_prep_free(&p);
    return ok ? EXIT_OK : EXIT_WRITE_FAILED;
}

static int run_bps_apply(const Options *o)
{
    uint8_t *src = NULL, *patch = NULL, *out = NULL;
    size_t src_size = 0, patch_size = 0, out_size = 0;
    const size_t max = 256u * 1024u * 1024u;
    int e = zen_read_file(o->bps_args[0], &src, &src_size, max);
    if (e != ZEN_FILE_OK) {
        zen_logf("bps: cannot read the source file (%s)\n", zen_file_error(e));
        return EXIT_USAGE;
    }
    e = zen_read_file(o->bps_args[1], &patch, &patch_size, max);
    if (e != ZEN_FILE_OK) {
        zen_logf("bps: cannot read the patch file (%s)\n", zen_file_error(e));
        free(src);
        return EXIT_USAGE;
    }
    BpsInfo info;
    int r = bps_apply(patch, patch_size, src, src_size, &out, &out_size, max, &info);
    free(src);
    free(patch);
    if (r != BPS_OK) {
        zen_logf("bps: %s\n", bps_error_string(r));
        return EXIT_BPS_BASE + r;
    }
    int ok = zen_write_file_atomic(o->bps_args[2], out, out_size) == ZEN_FILE_OK;
    free(out);
    if (!ok) {
        zen_logf("bps: cannot write the output file\n");
        return EXIT_WRITE_FAILED;
    }
    printf("bps: ok, %zu bytes written (target crc32 %08x)\n", out_size, (unsigned)info.target_crc);
    fflush(stdout);
    return EXIT_OK;
}

/* --unzip ZIP OUT: the game file the player would take from ZIP, unpacked
   and checked (also a test hook for the zip reader). */
static int run_unzip(const Options *o)
{
    uint8_t *data = NULL;
    size_t size = 0;
    ZipPick pick;
    int r = rom_unzip(o->unzip_args[0], ZIP_MAX_ENTRY_SIZE, &data, &size, &pick);
    char *name = pick.name ? zen_to_utf8(pick.name) : NULL;
    if (name)
        zen_logf("unzip: %s (%s, %u bytes packed, %u bytes, crc32 %08x%s)\n", name, zip_method_name(pick.method),
                 (unsigned)pick.packed_size, (unsigned)pick.size, (unsigned)pick.crc32,
                 pick.by_name ? "" : "; no .ngc/.ngp/.npc name: the only or largest file");
    free(name);
    free(pick.name);
    if (r < 0) {
        zen_logf("unzip: cannot open the file, or it is not a zip archive\n");
        return EXIT_ROM_UNREADABLE;
    }
    if (r != ZIP_OK) {
        zen_logf("unzip: %s\n", zip_error_string(r));
        return EXIT_ZIP_BASE + r;
    }
    int ok = zen_write_file_atomic(o->unzip_args[1], data, size) == ZEN_FILE_OK;
    free(data);
    if (!ok) {
        zen_logf("unzip: cannot write the output file\n");
        return EXIT_WRITE_FAILED;
    }
    printf("unzip: ok, %zu bytes written\n", size);
    fflush(stdout);
    return EXIT_OK;
}

static char *arg_utf8(const wchar_t *s)
{
    char *u = zen_to_utf8(s);
    return u ? u : _strdup("");
}

static int parse_args(int argc, wchar_t **argv, Options *o)
{
    memset(o, 0, sizeof(*o));
    o->frames = 600;
    o->png_scale = 2;
    o->log_level = -1;
    o->load_state_at = -1;
    o->save_state_at = -1;
    for (int i = 1; i < argc; i++) {
        const wchar_t *a = argv[i];
        int more = argc - i - 1;
        if (!wcscmp(a, L"--selftest")) o->selftest = 1;
        else if (!wcscmp(a, L"--patch") && more >= 1) o->patch = argv[++i];
        else if (!wcscmp(a, L"--frames") && more >= 1) o->frames = _wtoi(argv[++i]);
        else if (!wcscmp(a, L"--input") && more >= 1) o->input = arg_utf8(argv[++i]);
        else if (!wcscmp(a, L"--png") && more >= 1) o->png = argv[++i];
        else if (!wcscmp(a, L"--png-scale") && more >= 1) o->png_scale = _wtoi(argv[++i]);
        else if (!wcscmp(a, L"--save") && more >= 1) o->save = argv[++i];
        else if (!wcscmp(a, L"--load-state") && more >= 1) o->load_state = argv[++i];
        else if (!wcscmp(a, L"--load-state-at") && more >= 2) {
            o->load_state_at = _wtoi(argv[++i]);
            o->load_state_at_file = argv[++i];
        } else if (!wcscmp(a, L"--save-state") && more >= 2) {
            o->save_state_at = _wtoi(argv[++i]);
            o->save_state_file = argv[++i];
        }
        else if (!wcscmp(a, L"--untranslated")) o->untranslated = 1;
        else if (!wcscmp(a, L"--no-flash-commands")) o->no_flash_commands = 1;
        else if (!wcscmp(a, L"--write-patched") && more >= 1) o->write_patched = argv[++i];
        else if (!wcscmp(a, L"--exit-after") && more >= 1) o->exit_after = _wtof(argv[++i]);
        else if (!wcscmp(a, L"--console")) o->console = 1;
        else if (!wcscmp(a, L"--log") && more >= 1) o->log_level = _wtoi(argv[++i]);
        else if (!wcscmp(a, L"--bps-apply") && more >= 3) {
            o->bps_args[0] = argv[++i];
            o->bps_args[1] = argv[++i];
            o->bps_args[2] = argv[++i];
        }
        else if (!wcscmp(a, L"--unzip") && more >= 2) {
            o->unzip_args[0] = argv[++i];
            o->unzip_args[1] = argv[++i];
        }
        else if (!wcscmp(a, L"--help") || !wcscmp(a, L"-h") || !wcscmp(a, L"/?")) return 0;
        else if (a[0] == L'-' && a[1] == L'-') return -1;
        else if (!o->rom) o->rom = argv[i];
        else return -1;
    }
    if (o->png_scale < 1) o->png_scale = 1;
    if (o->png_scale > 16) o->png_scale = 16;
    if (o->frames < 0) o->frames = 0;
    return 1;
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmdline, int show)
{
    (void)prev;
    (void)cmdline;
    (void)show;
    int argc = 0;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (!argv) return EXIT_USAGE;

    Options o;
    int pr = parse_args(argc, argv, &o);
    int headless = o.selftest || o.write_patched || o.bps_args[0] || o.unzip_args[0];
    if (headless || o.exit_after > 0) g_zen_interactive = 0;
    /* A plain window start stays detached from any console (so Ctrl+C in the
       console it was started from cannot kill it without saving). */
    int console_ok = 0;
    if (headless || o.console || o.exit_after > 0 || pr <= 0) console_ok = zen_console_init(o.console);

    int code;
    if (pr <= 0) {
        /* usage: on the console when there is one, otherwise in a message box */
        if (console_ok) {
            char *u = zen_to_utf8(k_usage);
            zen_logf("%s%s", pr < 0 ? "zenobia: unknown or incomplete option\n" : "", u ? u : "");
            free(u);
        } else {
            MessageBoxW(NULL, k_usage, ZEN_TITLE, pr < 0 ? MB_OK | MB_ICONERROR : MB_OK | MB_ICONINFORMATION);
        }
        code = pr < 0 ? EXIT_USAGE : EXIT_OK;
    } else if (o.bps_args[0]) {
        code = run_bps_apply(&o);
    } else if (o.unzip_args[0]) {
        code = run_unzip(&o);
    } else if (o.selftest) {
        if (o.log_level >= 0) g_log_level = o.log_level;
        code = run_selftest(&o);
    } else if (o.write_patched) {
        code = run_write_patched(&o);
    } else {
        code = run_gui(&o, inst);
    }
    fflush(stdout);
    fflush(stderr);
    free(o.input);
    LocalFree(argv);
    return code;
}
