#!/usr/bin/env python3
"""Standalone tests for the pure blackjack engine (game.py).

These do NOT need Limnoria: run them with `python3 test_game.py`. They cover
the tricky cases that a random-play fuzz test will not reliably hit:
split, split aces, 21-after-split (not a blackjack), double down, natural
blackjack, dealer soft-17, ace valuation and the single-split rule.
"""

import random
import sys

import game


def rigged(seq):
    """A Table whose deck deals `seq` in order (popped from the end)."""
    class T(game.Table):
        def __init__(self, players, emit):
            self._seq = list(seq)
            game.Table.__init__(self, players, emit)

        def _draw(self):
            return self._seq.pop()
    return T


def deal(desired, players, actions=()):
    seq = list(reversed(desired))
    t = rigged(seq)(players, lambda s: None)
    for a in actions:
        getattr(t, a)()
    return t


def check(label, got, want):
    if got != want:
        print('FAIL: %s -> got %r, want %r' % (label, got, want))
        return 1
    return 0


fails = 0

# T1 split pair of 8s -> two hands
t = deal([('8', 'S'), ('8', 'H'), ('9', 'C'), ('9', 'D'), ('5', 'D'),
          ('3', 'C')], ['Youri'], ['split', 'stand', 'stand'])
fails += check('T1 hands count', len(t.hands['Youri']), 2)

# T2 split aces: one card each, both done
t = deal([('A', 'S'), ('A', 'H'), ('9', 'C'), ('9', 'D'), ('5', 'S'),
          ('6', 'H')], ['Youri'], ['split'])
fails += check('T2 aces done', [h.done for h in t.hands['Youri']], [True, True])
fails += check('T2 finished', t.finished, True)

# T3 21 after split is NOT a blackjack (regression for the fixed bug)
t = deal([('A', 'S'), ('A', 'H'), ('9', 'C'), ('9', 'D'), ('K', 'S'),
          ('Q', 'H')], ['Youri'], ['split'])
fails += check('T3 no bj after split',
               [h.blackjack for h in t.hands['Youri']], [False, False])
fails += check('T3 values', [h.value() for h in t.hands['Youri']], [21, 21])

# T4 natural blackjack wins instantly
t = deal([('A', 'S'), ('K', 'H'), ('9', 'C'), ('9', 'D')], ['Youri'])
t.begin_turn()
fails += check('T4 finished', t.finished, True)
fails += check('T4 result', t.results[0][1], 'win')

# T5 dealer stands on soft 17
t = deal([('10', 'S'), ('9', 'H'), ('A', 'S'), ('6', 'D')], ['Youri'],
         ['stand'])
fails += check('T5 dealer soft 17', game.hand_value(t.dealer), 17)

# T6 dealer draws on 16
t = deal([('10', 'S'), ('10', 'H'), ('10', 'C'), ('6', 'D'), ('9', 'S')],
         ['Youri'], ['stand'])
fails += check('T6 dealer draws to 25', game.hand_value(t.dealer), 25)

# T7 ace valuation
fails += check('T7 A+6', game.hand_value([('A', 'S'), ('6', 'H')]), 17)
fails += check('T7 A+6+10',
               game.hand_value([('A', 'S'), ('6', 'H'), ('10', 'D')]), 17)
fails += check('T7 A+A', game.hand_value([('A', 'S'), ('A', 'H')]), 12)
fails += check('T7 A+A+9',
               game.hand_value([('A', 'S'), ('A', 'H'), ('9', 'D')]), 21)

# T8 single split only (no re-split)
t = deal([('8', 'S'), ('8', 'H'), ('9', 'C'), ('9', 'D'), ('8', 'D'),
          ('8', 'C')], ['Youri'], ['split'])
fails += check('T8 no re-split', t._can_split(), False)

# T9 double down on 11 -> one card, 21
t = deal([('5', 'C'), ('6', 'D'), ('9', 'H'), ('9', 'S'), ('K', 'C')],
         ['Youri'], ['double_down'])
fails += check('T9 doubled', t.hands['Youri'][0].doubled, True)
fails += check('T9 value', t.hands['Youri'][0].value(), 21)

# T10 push
t = deal([('10', 'C'), ('9', 'H'), ('10', 'S'), ('9', 'D')], ['Youri'],
         ['stand'])
fails += check('T10 push', t.results[0][1], 'push')

# T11 double that busts
t = deal([('6', 'C'), ('6', 'D'), ('9', 'H'), ('9', 'S'), ('K', 'C')],
         ['Youri'], ['double_down'])
fails += check('T11 bust on double', t.results[0][1], 'loss')

# T12 multi-player order preserved
t = deal([('10', 'C'), ('9', 'H'), ('8', 'S'), ('10', 'D'), ('9', 'D'),
          ('8', 'C'), ('7', 'H'), ('7', 'S'), ('9', 'C'), ('9', 'S')],
         ['A', 'B', 'C'], ['stand', 'stand', 'stand'])
fails += check('T12 order',
               [r[0] for r in t.results], ['A', 'B', 'C'])

# T13 options offered on a pair
t = deal([('8', 'S'), ('8', 'H'), ('9', 'C'), ('9', 'D')], ['Youri'])
fails += check('T13 pair options', t._options(t.current_hand_obj()),
               ['hit', 'stand', 'split', 'double'])

# Fuzz: 2000 random games must all terminate without an exception
random.seed(7)
for _ in range(2000):
    n = random.randint(1, 6)
    players = ['P%d' % k for k in range(1, n + 1)]
    t = game.Table(players, lambda s: None)
    guard = 0
    while not t.finished:
        guard += 1
        if guard > 500:
            fails += check('fuzz no infinite loop', 'loop', 'finished')
            break
        opts = t._options(t.current_hand_obj())
        a = random.choice(opts)
        {'hit': t.hit, 'stand': t.stand, 'split': t.split,
         'double': t.double_down}[a]()

if fails:
    print('%d FAILURES' % fails)
    sys.exit(1)
print('All engine tests passed (13 cases + 2000 fuzz games).')
