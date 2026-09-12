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

### BlackJack — an IRC blackjack table (multiplayer, vs the dealer)

import json
import os
import random
import threading
import time

import supybot.ircmsgs as ircmsgs
import supybot.conf as conf
from supybot.commands import wrap, additional
import supybot.callbacks as callbacks
from supybot.i18n import PluginInternationalization

from . import game

_ = PluginInternationalization('BlackJack')

# Sharp remarks fired when a player is auto-stood after letting the move
# timer expire. Kept ASCII-only and short so they read well in any client.
SNARK = [
    "No answer in time. I'll stand for you. Sleeping at the table is a bold "
    "strategy.",
    "You snooze, you lose. Standing your hand. The dealer doesn't wait "
    "forever.",
    "Silence at the table. I'm standing you. Maybe rethink your life choices.",
    "I'll take that as a stand. Other players want to be crushed too.",
    "Cat got your tongue? Standing you. The cards won't play themselves.",
    "Time's up. Standing you. Poker faces are for poker.",
]

RESULT_WORD = {'win': 'won', 'loss': 'lost', 'push': 'push'}


class BlackJack(callbacks.Plugin):
    """Play blackjack against the dealer. Open a table, others join, everyone
    plays the dealer. Split, double down, and a win-rate leaderboard."""

    threaded = False
    priority = 100

    def __init__(self, irc):
        super().__init__(irc)
        self.games = {}       # channel -> game dict
        self.cooldowns = {}   # channel -> timestamp of last finished game
        self.last_cmd = {}    # (channel, nick) -> timestamp (command throttle)
        self.lock = threading.RLock()
        self._stats_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'scores.json')
        self.stats = self._load_stats()

    # ---------- persistence ----------
    def _load_stats(self):
        try:
            with open(self._stats_path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
        except (OSError, ValueError):
            pass
        return {}

    def _save_stats(self):
        try:
            tmp = self._stats_path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, sort_keys=True)
            os.replace(tmp, self._stats_path)
        except OSError:
            self.log.warning('BlackJack: could not write %s',
                             self._stats_path)

    def _rec(self, nick):
        key = nick.lower()
        s = self.stats.get(key)
        if s is None:
            s = {'name': nick, 'played': 0, 'won': 0, 'lost': 0, 'push': 0,
                 'blackjacks': 0, 'streak': 0, 'best': 0}
            self.stats[key] = s
        s['name'] = nick
        return s

    # ---------- output helpers ----------
    def _say(self, irc, channel, text):
        irc.queueMsg(ircmsgs.privmsg(channel, text))

    def _prefix(self, channel=None):
        """The command prefix the bot answers to (e.g. '@'), read from the
        live config so our messages show the same prefix the user must type."""
        chars = ''
        try:
            value = conf.supybot.reply.whenAddressedBy.chars
            try:
                chars = value.getSpecific(channel=channel)() if channel \
                    else value()
            except Exception:
                chars = value()
        except Exception:
            chars = ''
        chars = str(chars or '')
        return chars[0] if chars else '@'

    # ---------- command throttle (silent) ----------
    def _throttled(self, msg):
        """True if this nick acted in this channel less than the configured
        throttle ago. Silent: we never reply to a throttled command, so a
        spammer cannot make the bot flood the channel."""
        key = (msg.channel, msg.nick)
        now = time.time()
        secs = self.registryValue('commandThrottle')
        prev = self.last_cmd.get(key, 0)
        if now - prev < secs:
            return True
        self.last_cmd[key] = now
        return False

    # ---------- opening a table ----------
    def bj(self, irc, msg, args):
        """takes no arguments

        Opens a blackjack table in the current channel. You are seated first.
        Others have 60s to join; then the cards are dealt. One table per
        channel."""
        if not msg.channel:
            irc.error('Blackjack must be played in a channel, not in private.')
            return
        channel = msg.channel
        with self.lock:
            if channel in self.games:
                irc.error('There is already a blackjack game in this channel.')
                return
            cd = self.registryValue('gameCooldown')
            last = self.cooldowns.get(channel, 0)
            left = int(cd - (time.time() - last))
            if last and left > 0:
                irc.error('Table is on cooldown for another %d seconds.' % left)
                return
            jt = self.registryValue('joinTimeout')
            self.games[channel] = {
                'state': 'OPEN', 'players': [msg.nick], 'irc': irc,
                'opened_by': msg.nick, 'table': None, 'timer': None}
            self._arm(channel, jt, self._join_timeout)
        p = self._prefix(channel)
        self._say(irc, channel, 'Blackjack table open! %s is seated (1). '
                  'Anyone else: type %sbjjoin within %ds.'
                  % (msg.nick, p, self.registryValue('joinTimeout')))

    bj = wrap(bj, [])

    def bjjoin(self, irc, msg, args):
        """takes no arguments

        Takes a seat at an open blackjack table. Join order = play order."""
        if not msg.channel:
            irc.error('Join a table in a channel.')
            return
        channel = msg.channel
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'OPEN':
                irc.error('No open table here. Start one with %sbj.'
                          % self._prefix(msg.channel))
                return
            if msg.nick in g['players']:
                irc.error('You are already seated.')
                return
            maxp = self.registryValue('maxPlayers')
            if len(g['players']) >= maxp:
                irc.error('The table is full (%d players).' % maxp)
                return
            g['players'].append(msg.nick)
            seated = len(g['players'])
        self._say(irc, channel, '%s joins (%d). %d seats taken.'
                  % (msg.nick, seated, seated))

    bjjoin = wrap(bjjoin, [])

    def deal(self, irc, msg, args):
        """takes no arguments

        (Table opener only) Deals the cards immediately instead of waiting
        for the join window to expire."""
        if not msg.channel:
            irc.error('No table here.')
            return
        channel = msg.channel
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'OPEN':
                irc.error('No open table here.')
                return
            if msg.nick != g['opened_by']:
                irc.error('Only %s (who opened the table) can deal early.'
                          % g['opened_by'])
                return
        self._say(irc, channel, '%s gets impatient and deals early. Fine by me.'
                  % msg.nick)
        self._start_play(channel)

    deal = wrap(deal, [])

    # ---------- join timeout -> deal ----------
    def _join_timeout(self, channel):
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'OPEN':
                return
        self._say(g['irc'], channel, 'Join window over. Dealt cards.')
        self._start_play(channel)

    # ---------- play ----------
    def _start_play(self, channel):
        with self.lock:
            g = self.games.get(channel)
            if not g:
                return
            g['state'] = 'PLAYING'
            irc = g['irc']

            def emit(text):
                self._say(irc, channel, text)

            g['table'] = game.Table(list(g['players']), emit,
                                    prefix=self._prefix(channel))
            g['table'].begin_turn()
            self._arm(channel, self.registryValue('moveTimeout'),
                      self._move_timeout)
        if g['table'].finished:
            self._finalize(channel)

    def _arm(self, channel, seconds, callback):
        with self.lock:
            g = self.games.get(channel)
            if not g:
                return
            old = g.get('timer')
            if old:
                old.cancel()
            t = threading.Timer(seconds, callback, args=(channel,))
            t.daemon = True
            g['timer'] = t
            t.start()

    def _move_timeout(self, channel):
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'PLAYING':
                return
            irc = g['irc']
            table = g['table']
            if table.finished:
                return
            self._say(irc, channel, random.choice(SNARK))
        self._do(channel, 'stand')

    # ---------- player actions ----------
    def _is_my_turn(self, g, nick):
        return g['table'].current_nick().lower() == nick.lower()

    def _do(self, channel, action):
        """Runs a validated action and advances the table."""
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'PLAYING':
                return
            table = g['table']
            getattr(table, action)()
            if table.finished:
                self._finalize(channel)
            else:
                self._arm(channel, self.registryValue('moveTimeout'),
                          self._move_timeout)

    def _action(self, irc, msg, action, requires=None, deny=None):
        if not msg.channel:
            irc.error('Blackjack must be played in a channel.')
            return
        if self._throttled(msg):
            return
        channel = msg.channel
        with self.lock:
            g = self.games.get(channel)
            if not g or g['state'] != 'PLAYING':
                # No game: stay silent for random chatter; only complain if
                # the user clearly tried (we still reply once, harmless).
                g = None
        if not g:
            irc.error('No game in progress here.')
            return
        if not self._is_my_turn(g, msg.nick):
            # Not your turn: silent (antispam) — others cannot flood the
            # channel by hammering hit/stand.
            return
        if requires and not requires(g):
            irc.error(deny or 'You cannot do that now.')
            return
        self._do(channel, action)

    def hit(self, irc, msg, args):
        """takes no arguments

        Draws another card on your hand."""
        self._action(irc, msg, 'hit')

    hit = wrap(hit, [])

    def stand(self, irc, msg, args):
        """takes no arguments

        Ends your turn on the current hand."""
        self._action(irc, msg, 'stand')

    stand = wrap(stand, [])

    def split(self, irc, msg, args):
        """takes no arguments

        Splits a pair into two hands (single split only)."""
        self._action(
            irc, msg, 'split',
            requires=lambda g: g['table']._can_split(),
            deny='You can only split a matching pair, and only once.')

    split = wrap(split, [])

    def double(self, irc, msg, args):
        """takes no arguments

        Doubles down: one more card, then your turn on that hand ends."""
        def ok(g):
            h = g['table'].current_hand_obj()
            return len(h.cards) == 2 and not h.doubled
        self._action(irc, msg, 'double_down', requires=ok,
                     deny='You can only double down on your first two cards.')

    double = wrap(double, [])

    # ---------- finalize ----------
    def _finalize(self, channel):
        with self.lock:
            g = self.games.pop(channel, None)
            if not g:
                return
            irc = g['irc']
            self.cooldowns[channel] = time.time()
            table = g['table']
            # per-nick tally for THIS round
            tally = {}
            order = []
            for (nick, outcome, value, bj) in table.results:
                s = self._rec(nick)
                s['played'] += 1
                if outcome == 'win':
                    s['won'] += 1
                    s['streak'] = s['streak'] + 1 if s['streak'] > 0 else 1
                elif outcome == 'loss':
                    s['lost'] += 1
                    s['streak'] = s['streak'] - 1 if s['streak'] < 0 else -1
                else:
                    s['push'] += 1
                if bj:
                    s['blackjacks'] += 1
                s['best'] = max(s['best'], s['streak'])
                t = tally.setdefault(nick, {'win': 0, 'loss': 0, 'push': 0,
                                            'hands': 0})
                if nick not in order:
                    order.append(nick)
                t['hands'] += 1
                t[outcome] = t.get(outcome, 0) + 1
            self._save_stats()
            cd = self.registryValue('gameCooldown')
        # report out of the lock
        for nick in order:
            t = tally[nick]
            parts = []
            if t['win']:
                parts.append('%d won' % t['win'])
            if t['loss']:
                parts.append('%d lost' % t['loss'])
            if t['push']:
                parts.append('%d push' % t['push'])
            s = self._rec(nick)
            rate = (100.0 * s['won'] / s['played']) if s['played'] else 0.0
            self._say(irc, channel, '%s: %s (this round). Win rate: %.0f%% '
                      '(%d/%d).' % (nick, ', '.join(parts), rate,
                                    s['won'], s['played']))
        self._say(irc, channel, 'Round over. New table possible in %ds.'
                  % cd)

    # ---------- stats ----------
    def bjstats(self, irc, msg, args, nick):
        """[<nick>]

        Shows blackjack stats for you or for <nick>."""
        who = str(nick).strip() if nick else msg.nick
        s = self.stats.get(who.lower())
        if not s:
            irc.reply('No blackjack stats for %s.' % who)
            return
        rate = (100.0 * s['won'] / s['played']) if s['played'] else 0.0
        irc.reply('Stats for %s: %d played | %d won (%.0f%%) | %d lost | '
                  '%d push | %d blackjacks | best streak %d | current streak '
                  '%d' % (s['name'], s['played'], s['won'], rate, s['lost'],
                          s['push'], s['blackjacks'], s['best'], s['streak']))

    bjstats = wrap(bjstats, [additional('something')])

    def bjtop(self, irc, msg, args):
        """takes no arguments

        Shows the blackjack leaderboard by win rate (min. hands required)."""
        minh = self.registryValue('minHandsForTop')
        rows = [s for s in self.stats.values() if s['played'] >= minh]
        rows.sort(key=lambda s: (s['won'] / s['played'], s['won']),
                  reverse=True)
        if not rows:
            irc.reply('No players with at least %d hands yet.' % minh)
            return
        out = ['Top blackjack players (min. %d hands, by win rate):' % minh]
        for i, s in enumerate(rows[:10], 1):
            rate = 100.0 * s['won'] / s['played']
            out.append(' %2d. %s  %.0f%%  (%dW-%dL-%dP of %d)'
                       % (i, s['name'], rate, s['won'], s['lost'], s['push'],
                          s['played']))
        for line in out:
            irc.reply(line)

    bjtop = wrap(bjtop, [])


Class = BlackJack
