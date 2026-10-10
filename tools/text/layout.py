"""Word wrapping and pagination for English message text.

Widths come from the compiled variable-width font, so layout matches what the
renderer draws. Inserted values ([NAME], [NUM]) are measured pessimistically.
"""
import os
import re

from .encoding_en import ENCODE, CONTROLS

LINE_WIDTH = 144          # 18 tiles (opening scenes)
STAGE_LINE_WIDTH = 136    # 17 tiles: stage scenes put the text one cell further right


def line_width_for(addr):
    """Usable line width for the message at addr: the opening/prologue window
    (bank 0x29) has 18 columns, the stage dialogue window 17 (the original
    never puts more than 17 characters on a stage dialogue line)."""
    return LINE_WIDTH if addr >> 16 == 0x29 else STAGE_LINE_WIDTH
LINES_PER_PAGE = 3
TAG_WIDTH = {'[NAME]': 54,  # longest 9-character name we allow
             '[NUM]': 25}   # up to 5 digits

_widths = None
_TAG = re.compile(r'\[(?:NAME|NUM)\]')


def widths():
    global _widths
    if _widths is None:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        path = os.path.join(root, 'build', 'font', 'vwf_widths.bin')
        if not os.path.exists(path):
            from . import fontc
            fontc.build(os.path.join(root, 'assets', 'font', 'vwf8.txt'), os.path.dirname(path))
        with open(path, 'rb') as f:
            _widths = f.read()
    return _widths


def text_width(s):
    """Pixel width of a run of text (may contain [NAME]/[NUM] tags)."""
    w = widths()
    total, i = 0, 0
    while i < len(s):
        m = _TAG.match(s, i)
        if m:
            total += TAG_WIDTH[m.group(0)]
            i = m.end()
            continue
        code = ENCODE.get(s[i])
        if code is None:
            raise ValueError('no English code for %r' % s[i])
        total += w[code]
        i += 1
    return total


def wrap_line(line, width=LINE_WIDTH):
    """Wrap one source line into display lines that fit `width` pixels."""
    space = text_width(' ')
    lines, cur, cur_w = [], [], 0
    for word in line.split():
        ww = text_width(word)
        if ww > width:
            raise ValueError('word too wide for a line: %r' % word)
        need = ww if not cur else cur_w + space + ww
        if cur and need > width:
            lines.append(' '.join(cur))
            cur, cur_w = [word], ww
        else:
            cur.append(word)
            cur_w = need
    lines.append(' '.join(cur))
    return lines


def paginate(text, width=LINE_WIDTH, per_page=LINES_PER_PAGE):
    """Source text -> list of pages, each a list of display lines.

    Each source line starts a new display line; a line '---' starts a new page.
    """
    pages, cur = [], []
    for src in text.split('\n'):
        if src.strip() == '---':
            if cur:
                pages.append(cur)
            cur = []
            continue
        for l in wrap_line(src.strip(), width):
            if len(cur) == per_page:
                pages.append(cur)
                cur = []
            cur.append(l)
    if cur:
        pages.append(cur)
    return pages
