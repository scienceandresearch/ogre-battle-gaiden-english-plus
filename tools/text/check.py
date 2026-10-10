"""Report layout of translated messages: pages, lines and pixel widths.

Usage: python -m tools.text.check translation/en/script.txt [--all]
Flags entries that need more than one page (so a translator can tighten them).
Stage dialogue lines are 136 px wide, opening/prologue lines 144 px.
"""
import sys

from .insert import read_translations
from .layout import paginate, text_width, line_width_for


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    entries = read_translations(sys.argv[1])
    show_all = '--all' in sys.argv
    multi = 0
    for addr, text in sorted(entries.items()):
        pages = paginate(text, line_width_for(addr))
        if len(pages) > 1:
            multi += 1
        if show_all or len(pages) > 1:
            print('@%06X  %d page(s)' % (addr, len(pages)))
            for pi, page in enumerate(pages):
                for line in page:
                    print('   %3dpx |%s' % (text_width(line), line))
                if pi != len(pages) - 1:
                    print('   ------')
    print('%d entries, %d need more than one page (136 px stage / 144 px opening lines)' % (len(entries), multi))


if __name__ == '__main__':
    main()
