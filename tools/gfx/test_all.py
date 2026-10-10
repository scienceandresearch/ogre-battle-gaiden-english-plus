"""Run every test module of the graphics tools.

Usage: python -m tools.gfx.test_all [ROM] [-v] [-k TEXT] [--timeout SECONDS]

Each tools/gfx/test_*.py (except this file) runs in its own process, as
`python -m tools.gfx.test_<name> [ROM]` from the repository root, one after
the other; a module passes when it exits with status 0. ROM (normally
rom/baserom.ngc) is handed to every module; modules that do not need it
ignore it. The environment is passed on (NGP_HARNESS for the harness checks).

Prints one line per module with its own last line (its summary), then the
output of every failing module (-v: of every module) and the totals. Exit
status 1 when a module failed. -k TEXT runs only the modules whose name
contains TEXT.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
PACKAGE = __package__ or 'tools.gfx'           # also right when run with python -m
SELF = os.path.splitext(os.path.basename(__file__))[0]


def modules():
    """The test modules of the package: test_*.py, sorted, without this one."""
    return sorted(f[:-3] for f in os.listdir(HERE)
                  if f.startswith('test_') and f.endswith('.py') and f[:-3] != SELF)


def run_module(name, rom=None, timeout=1800):
    """(exit status or None on a timeout, output, seconds)."""
    cmd = [sys.executable, '-m', '%s.%s' % (PACKAGE, name)] + ([rom] if rom else [])
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace', env=env,
                           timeout=timeout)
        code, out = p.returncode, p.stdout + (('\n' + p.stderr) if p.stderr.strip() else '')
    except subprocess.TimeoutExpired as e:
        partial = e.stdout or ''
        if isinstance(partial, bytes):
            partial = partial.decode('utf-8', 'replace')
        code, out = None, partial + '\n(timed out after %d s)' % timeout
    return code, out, time.time() - t0


def last_line(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ''


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m tools.gfx.test_all',
                                 description='Run every tools/gfx/test_*.py module.')
    ap.add_argument('rom', nargs='?', help='the original ROM (rom/baserom.ngc), handed to every module')
    ap.add_argument('-v', '--verbose', action='store_true', help='print the output of every module')
    ap.add_argument('-k', metavar='TEXT', help='only the modules whose name contains TEXT')
    ap.add_argument('--timeout', type=int, default=1800, help='seconds per module (default 1800)')
    args = ap.parse_args(argv)
    if args.rom and not os.path.isfile(args.rom):
        print('error: %s does not exist' % args.rom)
        return 2
    rom = os.path.abspath(args.rom) if args.rom else None
    names = [n for n in modules() if not args.k or args.k in n]
    if not names:
        print('no test modules%s' % (' matching %r' % args.k if args.k else ''))
        return 1
    width = max(len(n) for n in names)
    failed, outputs = [], []
    for name in names:
        code, out, secs = run_module(name, rom, args.timeout)
        state = 'ok' if code == 0 else ('TIMEOUT' if code is None else 'FAIL')
        print('%-*s  %-7s %6.1f s  %s' % (width, name, state, secs, last_line(out)), flush=True)
        if code != 0:
            failed.append(name)
        if code != 0 or args.verbose:
            outputs.append((name, state, out))
    for name, state, out in outputs:
        print('\n===== %s (%s)' % (name, state))
        print(out.rstrip())
    print('\n%d test module%s, %d failed%s' % (len(names), '' if len(names) == 1 else 's', len(failed),
                                               ': ' + ', '.join(failed) if failed else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
