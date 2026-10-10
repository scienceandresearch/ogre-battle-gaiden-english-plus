"""Character table for the game's 1-byte text encoding (font at ROM 0x200C79 + 16*code).

Codes 0x00-0xDC are glyphs/layout; 0xDD-0xFF are control codes.
"""

HIRA = 'あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん'
HIRA_V = 'がぎぐげござじずぜぞだぢづでどばびぶべぼ'
HIRA_P = 'ぱぴぷぺぽ'
HIRA_S = 'ぁぃぅぇぉゃゅょっ'
KATA = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン'
KATA_V = 'ガギグゲゴザジズゼゾダヂヅデドバビブベボ'
KATA_P = 'パピプペポ'
KATA_S = 'ァィゥェォャュョッ'
PUNCT = '「」?!、。ヴ.,・‥/+-=:%&『』…©　'

DECODE = {0x00: '\n', 0x01: ' '}
_code = 0x02
for ch in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ' + HIRA + HIRA_V + HIRA_P + HIRA_S + KATA + KATA_V + KATA_P + KATA_S + PUNCT:
    DECODE[_code] = ch
    _code += 1
assert _code == 0xDD, hex(_code)

CONTROL = {0xDD: '[NAME]', 0xDE: '[NUM]'}

ENCODE = {v: k for k, v in DECODE.items()}


def decode_bytes(bs):
    out = []
    for b in bs:
        if b in DECODE:
            out.append(DECODE[b])
        elif b in CONTROL:
            out.append(CONTROL[b])
        else:
            out.append('[%02X]' % b)
    return ''.join(out)
