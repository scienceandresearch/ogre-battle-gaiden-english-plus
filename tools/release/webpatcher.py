"""Make the one-file web patcher, "Patch your game.html".

    python -m tools.release.webpatcher [--bps build/ogre_en.bps] [--out FILE]

The page (template: tools/release/patcher.html) lets anyone turn their own copy
of the original game into the English ROM with a browser: choose the file (a
.zip works too), click "Save the English game". It works offline by
double-clicking the file, on any system, and its Content-Security-Policy
forbids all network access, so the game file never leaves the computer. The
English patch is built in as base64 (ogre_en.bps holds no data from the game;
the build audits it), with the SHA-1 of the original and of the English ROM:
the page checks the file before and after patching.

tools/release/package.py puts the page into the release zip next to
zenobia.exe; tools/release/test_webpatcher.py runs the page's own script in
Node against the real ROM.
"""
import argparse
import base64
import hashlib
import os
import re

from ..recomp.rom import EXPECTED_SHA1

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEMPLATE = 'tools/release/patcher.html'
PAGE_NAME = 'Patch your game.html'
ROM_SIZE = 2 * 1024 * 1024


class WebPatcherError(Exception):
    pass


def build(patch, english_sha1, version, original_sha1=EXPECTED_SHA1, original_size=ROM_SIZE, repo=REPO):
    """The page as UTF-8 bytes, with the patch and checksums filled in."""
    with open(os.path.join(repo, TEMPLATE), encoding='utf-8') as f:
        text = f.read()
    fields = {
        'BPS_BASE64': base64.b64encode(patch).decode('ascii'),
        'ORIGINAL_SHA1': original_sha1.lower(),
        'ENGLISH_SHA1': english_sha1.lower(),
        'ORIGINAL_SIZE': format(original_size, ','),
        'ORIGINAL_SIZE_BYTES': str(original_size),
        'VERSION': version,
    }
    for key, value in fields.items():
        text = text.replace('@%s@' % key, value)
    left = sorted(set(re.findall(r'@[A-Z0-9_]+@', text)))
    if left:
        raise WebPatcherError('%s has unfilled fields: %s' % (TEMPLATE, ', '.join(left)))
    return text.encode('utf-8')


def script_of(page):
    """The page's <script> text (the test runs it in Node)."""
    text = page.decode('utf-8') if isinstance(page, bytes) else page
    m = re.search(r'<script>(.*)</script>', text, re.S)
    if not m:
        raise WebPatcherError('the page has no <script>')
    return m.group(1)


def main():
    ap = argparse.ArgumentParser(prog='python -m tools.release.webpatcher')
    ap.add_argument('--bps', default=os.path.join(REPO, 'build', 'ogre_en.bps'))
    ap.add_argument('--out', default=os.path.join(REPO, 'build', PAGE_NAME))
    ap.add_argument('--version', default=None, help='shown on the page (default: VERSION + "-dev")')
    args = ap.parse_args()
    patch = open(args.bps, 'rb').read()
    sha1_path = os.path.splitext(args.bps)[0] + '.sha1'
    english_sha1 = open(sha1_path).read().split()[0]
    version = args.version
    if version is None:
        version = open(os.path.join(REPO, 'VERSION')).read().strip() + '-dev'
    page = build(patch, english_sha1, version)
    with open(args.out, 'wb') as f:
        f.write(page)
    print('wrote %s (%s bytes; patch %s bytes; English SHA-1 %s)' % (
        args.out, format(len(page), ','), format(len(patch), ','), english_sha1))


if __name__ == '__main__':
    main()
