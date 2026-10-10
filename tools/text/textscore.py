"""Statistical check that a byte string is natural Japanese in the game's encoding.

A character-bigram model, interpolated with a unigram model so that rare but
natural character pairs are not punished too hard, is trained on strings that
are known to be real (found by the script walker) and compared against a
uniform background. Scores are average log-likelihood ratios per byte: real
dialogue scores about 1.7-3.9, bytecode/graphics data decoded as text mostly
scores below 0.
"""
import math
from collections import Counter

from .charmap import DECODE

_START = 0x100
_TAGS = (0xDD, 0xDE)    # [NAME] / [NUM] substitutions are valid text too


def _printable_ratio(bs):
    return sum(1 for b in bs if b in DECODE or b in _TAGS) / len(bs)


class TextScorer:
    def __init__(self, known_strings, lam=0.7):
        self.uni = Counter()
        self.bi = Counter()
        for s in known_strings:
            prev = _START
            self.uni[_START] += 1
            for b in s:
                self.uni[b] += 1
                self.bi[(prev, b)] += 1
                prev = b
        self.total = sum(v for k, v in self.uni.items() if k != _START)
        self.vocab = 0xDF
        self.lam = lam

    def logprob(self, bs):
        """Average log-likelihood ratio per byte vs. a uniform model."""
        if not bs:
            return -99.0
        lp = 0.0
        prev = _START
        for b in bs:
            if b >= 0xDF:
                return -99.0
            pu = (self.uni[b] + 0.1) / (self.total + 0.1 * self.vocab)
            pb = self.bi[(prev, b)] / self.uni[prev] if self.uni[prev] else 0.0
            p = self.lam * pb + (1 - self.lam) * pu
            lp += math.log(p * self.vocab)
            prev = b
        return lp / len(bs)

    def looks_like_text(self, bs, threshold=1.5):
        if len(bs) < 2:
            return False
        if _printable_ratio(bs) < 0.9:
            return False
        return self.logprob(bs) >= threshold

    def strings_look_like_text(self, strings, combined=1.4, floor=0.8, short=8):
        """Judge several strings from one script chunk together: the
        length-weighted mean score must reach `combined` and no string of at
        least `short` bytes may fall below `floor` (short exclamations such as
        "[NAME]\u300e!!" score low on their own and only count via the mean)."""
        if not strings:
            return True
        total, weight = 0.0, 0
        for bs in strings:
            if not bs:
                continue
            if _printable_ratio(bs) < 0.9:
                return False
            lp = self.logprob(bs)
            if lp < floor and len(bs) >= short:
                return False
            total += lp * len(bs)
            weight += len(bs)
        return weight == 0 or total / weight >= combined
