"""Character table for the game's 1-byte text encoding (font at ROM 0x200C79 + 16*code).

Codes 0x00-0xDC are glyphs/layout; 0xDD-0xFF are control codes.
"""

HIRA = '\u3042\u3044\u3046\u3048\u304a\u304b\u304d\u304f\u3051\u3053\u3055\u3057\u3059\u305b\u305d\u305f\u3061\u3064\u3066\u3068\u306a\u306b\u306c\u306d\u306e\u306f\u3072\u3075\u3078\u307b\u307e\u307f\u3080\u3081\u3082\u3084\u3086\u3088\u3089\u308a\u308b\u308c\u308d\u308f\u3092\u3093'
HIRA_V = '\u304c\u304e\u3050\u3052\u3054\u3056\u3058\u305a\u305c\u305e\u3060\u3062\u3065\u3067\u3069\u3070\u3073\u3076\u3079\u307c'
HIRA_P = '\u3071\u3074\u3077\u307a\u307d'
HIRA_S = '\u3041\u3043\u3045\u3047\u3049\u3083\u3085\u3087\u3063'
KATA = '\u30a2\u30a4\u30a6\u30a8\u30aa\u30ab\u30ad\u30af\u30b1\u30b3\u30b5\u30b7\u30b9\u30bb\u30bd\u30bf\u30c1\u30c4\u30c6\u30c8\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d2\u30d5\u30d8\u30db\u30de\u30df\u30e0\u30e1\u30e2\u30e4\u30e6\u30e8\u30e9\u30ea\u30eb\u30ec\u30ed\u30ef\u30f2\u30f3'
KATA_V = '\u30ac\u30ae\u30b0\u30b2\u30b4\u30b6\u30b8\u30ba\u30bc\u30be\u30c0\u30c2\u30c5\u30c7\u30c9\u30d0\u30d3\u30d6\u30d9\u30dc'
KATA_P = '\u30d1\u30d4\u30d7\u30da\u30dd'
KATA_S = '\u30a1\u30a3\u30a5\u30a7\u30a9\u30e3\u30e5\u30e7\u30c3'
PUNCT = '\u300c\u300d?!\u3001\u3002\u30f4.,\u30fb\u2025/+-=:%&\u300e\u300f\u2026\xa9\u3000'

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
