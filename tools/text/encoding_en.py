"""English text encoding used by the translation patch.

Layout codes and controls keep their original meaning:
  0x00 newline (0x00 0x00 ends a window buffer)   0x01 space
  0x02-0x0B '0'-'9'       0x0C-0x25 'A'-'Z'       (same as the original font)
  0xDD [NAME] insert       0xDE [NUM] insert       0xDF-0xFF string terminators
New codes replace the kana range:
  0x26-0x3F 'a'-'z', then punctuation from 0x40.
The original punctuation codes are kept as aliases for the same glyphs so any
text we do not re-encode still renders sensibly.
"""

PUNCT = [
    ('.', '.'), (',', ','), ('!', '!'), ('?', '?'), ("'", "'"), ('"', '"'), (':', ':'), (';', ';'),
    ('-', '-'), ('(', '('), (')', ')'), ('/', '/'), ('&', '&'), ('%', '%'), ('+', '+'), ('=', '='),
    ('…', 'ELLIPSIS'), ('“', 'LQUOTE'), ('*', '*'), ('~', '~'), ('[', '['), (']', ']'),
]

ENCODE = {'\n': 0x00, ' ': 0x01}
GLYPH_OF_CODE = {0x01: 'SPACE'}
for i, ch in enumerate('0123456789'):
    ENCODE[ch] = 0x02 + i
    GLYPH_OF_CODE[0x02 + i] = ch
for i, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
    ENCODE[ch] = 0x0C + i
    GLYPH_OF_CODE[0x0C + i] = ch
for i, ch in enumerate('abcdefghijklmnopqrstuvwxyz'):
    ENCODE[ch] = 0x26 + i
    GLYPH_OF_CODE[0x26 + i] = ch
for i, (ch, glyph) in enumerate(PUNCT):
    ENCODE[ch] = 0x40 + i
    GLYPH_OF_CODE[0x40 + i] = glyph
ENCODE['”'] = ENCODE['"']
ENCODE['’'] = ENCODE["'"]
ENCODE['‘'] = ENCODE["'"]

# Original punctuation codes -> English glyphs (aliases)
ALIASES = {0xC8: '?', 0xC9: '!', 0xCD: '.', 0xCE: ',', 0xCA: ',', 0xCB: '.', 0xD1: '/', 0xD2: '+',
           0xD3: '-', 0xD4: '=', 0xD5: ':', 0xD6: '%', 0xD7: '&', 0xDA: 'ELLIPSIS', 0xD0: 'ELLIPSIS',
           0xC6: 'LQUOTE', 0xC7: '"', 0xD8: 'LQUOTE', 0xD9: '"',
           0xCF: '.',       # the original's middle dot: separator in the save-file list ("1.")
           0xDC: 'SPACE'}   # full-width space: blank glyph that takes a tile (names, padding)
for code, glyph in ALIASES.items():
    GLYPH_OF_CODE[code] = glyph

CONTROLS = {'[NAME]': 0xDD, '[NUM]': 0xDE}


class EncodeError(Exception):
    pass


def encode(text):
    """Encode English text; [NAME] and [NUM] become insert codes."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text[i] == '[':
            j = text.find(']', i)
            tag = text[i:j + 1]
            if tag in CONTROLS:
                out.append(CONTROLS[tag])
                i = j + 1
                continue
        ch = text[i]
        if ch not in ENCODE:
            raise EncodeError('character %r has no English code' % ch)
        out.append(ENCODE[ch])
        i += 1
    return bytes(out)


DECODE = {}
for ch, code in ENCODE.items():
    DECODE.setdefault(code, ch)
