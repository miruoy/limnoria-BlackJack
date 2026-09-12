# Copyright (C) 2026  Youri Matthys (miruoy)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

"""Pure blackjack engine for the BlackJack Limnoria plugin.

No Limnoria imports here on purpose: this module is fully testable
standalone (see test_game.py / the standalone self-test at the bottom).
The IRC glue lives in plugin.py and only drives this engine.
"""

import random

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
SUITS = ['Clubs', 'Diamonds', 'Hearts', 'Spades']
RANK_NAMES = {'J': 'Jack', 'Q': 'Queen', 'K': 'King', 'A': 'Ace'}


def make_deck():
    return [(r, s) for s in SUITS for r in RANKS]


def card_name(card):
    rank, suit = card
    return '%s of %s' % (RANK_NAMES.get(rank, rank), suit)


def hand_str(cards):
    return ', '.join(card_name(c) for c in cards)


def card_value(rank):
    if rank == 'A':
        return 11
    if rank in ('J', 'Q', 'K'):
        return 10
    return int(rank)


def hand_value(cards):
    """Best value of a hand: aces count 11 unless that busts, then 1."""
    total = sum(card_value(c[0]) for c in cards)
    aces = sum(1 for c in cards if c[0] == 'A')
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards):
    return len(cards) == 2 and hand_value(cards) == 21


class Hand(object):
    def __init__(self, cards):
        self.cards = list(cards)
        self.done = False
        self.doubled = False
        # A true blackjack: natural 21 on the initial two cards. Reset to
        # False after a split (a 21 made of A+10 is NOT a blackjack).
        self.blackjack = is_blackjack(self.cards)

    def value(self):
        return hand_value(self.cards)


class Table(object):
    """One blackjack table: many players, all against one dealer.

    Emits human-readable lines via ``emit`` (a callable taking a str).
    ``players`` is the join order; that is also the play order.
    """

    def __init__(self, players, emit, prefix=''):
        self.emit = emit
        self.prefix = prefix
        self.players = list(players)
        self.deck = make_deck()
        random.shuffle(self.deck)
        self.hands = {}        # nick -> [Hand, ...]
        self.dealer = []
        self.current_idx = 0
        self.current_hand = 0
        self.state = 'PLAYING'
        self.finished = False
        self.results = []      # (nick, 'win'|'loss'|'push', value, blackjack)
        self._deal()

    # ---------- dealing ----------
    def _draw(self):
        return self.deck.pop()

    def _deal(self):
        for nick in self.players:
            self.hands[nick] = [Hand([self._draw(), self._draw()])]
        self.dealer = [self._draw(), self._draw()]
        self.emit('Cards are dealt. Play order: %s.' % ', '.join(self.players))
        self.emit('Dealer shows: %s, ??' % card_name(self.dealer[0]))
        for nick in self.players:
            h = self.hands[nick][0]
            self.emit('%s: %s  = %d' % (nick, hand_str(h.cards), h.value()))

    # ---------- turn helpers ----------
    def current_nick(self):
        return self.players[self.current_idx]

    def current_hand_obj(self):
        return self.hands[self.current_nick()][self.current_hand]

    def begin_turn(self):
        nick = self.current_nick()
        hand = self.current_hand_obj()
        if hand.blackjack:
            self.emit('%s has a blackjack!' % nick)
            hand.done = True
            self._next_turn()
            return
        label = nick
        if len(self.hands[nick]) > 1:
            label = '%s - Hand %d' % (nick, self.current_hand + 1)
        opts = self._options(hand)
        self.emit('%s: %s  = %d' % (label, hand_str(hand.cards), hand.value()))
        self.emit('Your move, %s? [ %s ]'
                  % (nick, ' | '.join(self.prefix + o for o in opts)))

    def _options(self, hand):
        opts = ['hit', 'stand']
        if len(hand.cards) == 2 and not hand.doubled:
            if self._can_split():
                opts.append('split')
            opts.append('double')
        return opts

    def _can_split(self):
        nick = self.current_nick()
        hands = self.hands[nick]
        hand = self.current_hand_obj()
        # Single split only: a player may never hold more than 2 hands.
        if len(hands) >= 2:
            return False
        return (len(hand.cards) == 2
                and hand.cards[0][0] == hand.cards[1][0])

    # ---------- actions ----------
    def hit(self):
        nick = self.current_nick()
        hand = self.current_hand_obj()
        hand.cards.append(self._draw())
        self.emit('%s hits: %s  = %d' % (nick, hand_str(hand.cards),
                                         hand.value()))
        if hand.value() > 21:
            self.emit('%s busts with %d!' % (nick, hand.value()))
            hand.done = True
            self._next_turn()
        elif hand.value() == 21:
            hand.done = True
            self._next_turn()

    def stand(self):
        nick = self.current_nick()
        hand = self.current_hand_obj()
        self.emit('%s stands on %d.' % (nick, hand.value()))
        hand.done = True
        self._next_turn()

    def double_down(self):
        nick = self.current_nick()
        hand = self.current_hand_obj()
        hand.doubled = True
        hand.cards.append(self._draw())
        self.emit('%s doubles down: %s  = %d' % (nick, hand_str(hand.cards),
                                                 hand.value()))
        if hand.value() > 21:
            self.emit('%s busts with %d!' % (nick, hand.value()))
        hand.done = True
        self._next_turn()

    def split(self):
        nick = self.current_nick()
        hands = self.hands[nick]
        hand = self.current_hand_obj()
        moved = hand.cards.pop()
        new_hand = Hand([moved, self._draw()])
        new_hand.blackjack = False  # a 21 made after a split is not a blackjack
        hand.cards.append(self._draw())
        hand.blackjack = False
        hands.insert(self.current_hand + 1, new_hand)
        self.emit('%s splits the %ss. Each hand draws a new card.'
                  % (nick, hand.cards[0][0]))
        self.emit('%s - Hand 1: %s  = %d' % (nick, hand_str(hand.cards),
                                             hand.value()))
        self.emit('%s - Hand 2: %s  = %d' % (nick, hand_str(new_hand.cards),
                                             new_hand.value()))
        if hand.cards[0][0] == 'A':
            # Split aces: one card each, no further hits.
            self.emit('Split aces get one card each and no more hits.')
            hand.done = True
            new_hand.done = True
            self._next_turn()
        else:
            self.begin_turn()

    # ---------- flow ----------
    def _next_turn(self):
        nick = self.current_nick()
        hands = self.hands[nick]
        nxt = self.current_hand + 1
        while nxt < len(hands) and hands[nxt].done:
            nxt += 1
        if nxt < len(hands):
            self.current_hand = nxt
            self.begin_turn()
            return
        pi = self.current_idx + 1
        while pi < len(self.players) and all(h.done
                                             for h in self.hands[self.players[pi]]):
            pi += 1
        if pi < len(self.players):
            self.current_idx = pi
            self.current_hand = 0
            self.begin_turn()
            return
        self._dealer_play()

    def _dealer_play(self):
        self.state = 'DEALER'
        while hand_value(self.dealer) < 17:
            self.dealer.append(self._draw())
        dv = hand_value(self.dealer)
        self.emit('Dealer: %s  = %d' % (hand_str(self.dealer), dv))
        self._results()

    def _results(self):
        dv = hand_value(self.dealer)
        dealer_bj = is_blackjack(self.dealer)
        dealer_bust = dv > 21
        for nick in self.players:
            for i, hand in enumerate(self.hands[nick]):
                label = nick
                if len(self.hands[nick]) > 1:
                    label = '%s (Hand %d)' % (nick, i + 1)
                hv = hand.value()
                if hv > 21:
                    outcome = 'loss'
                    why = 'bust'
                elif hand.blackjack and not dealer_bj:
                    outcome = 'win'
                    why = 'blackjack!'
                elif dealer_bj:
                    outcome = 'loss'
                    why = 'dealer blackjack'
                elif dealer_bust:
                    outcome = 'win'
                    why = 'dealer busts'
                elif hv > dv:
                    outcome = 'win'
                    why = 'beats dealer'
                elif hv == dv:
                    outcome = 'push'
                    why = 'push'
                else:
                    outcome = 'loss'
                    why = 'dealer wins'
                self.emit('%s: %s  = %d  -> %s' % (label, hand_str(hand.cards),
                                                   hv, why))
                self.results.append((nick, outcome, hv, hand.blackjack))
        self.finished = True
        self.state = 'DONE'
