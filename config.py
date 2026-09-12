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

### BlackJack — configuration

import supybot.conf as conf
import supybot.registry as registry
from supybot.i18n import PluginInternationalization
_ = PluginInternationalization('BlackJack')

BlackJack = conf.registerPlugin('BlackJack')

# NOTE: these are registered as GLOBAL values, and the plugin reads them with
# self.registryValue('name') (no channel). Limnoria's registry cannot upgrade
# an already-registered entry from global to channel-specific (Group.register
# explicitly refuses to re-register), so channel-specific values would only
# ever work on a brand-new bot. Global values always work.

conf.registerGlobalValue(BlackJack, 'moveTimeout',
    registry.Integer(15, _("""Seconds a player has to make a move before the
    bot auto-stands for them.""")))

conf.registerGlobalValue(BlackJack, 'joinTimeout',
    registry.Integer(60, _("""Seconds the join window stays open after a table
    is opened with the bj command.""")))

conf.registerGlobalValue(BlackJack, 'gameCooldown',
    registry.Integer(120, _("""Seconds before a new table can be opened in the
    same channel after a game ends (anti-spam).""")))

conf.registerGlobalValue(BlackJack, 'maxPlayers',
    registry.Integer(6, _("""Maximum number of players at one table.""")))

conf.registerGlobalValue(BlackJack, 'minHandsForTop',
    registry.Integer(15, _("""Minimum number of hands played for a player to
    appear in the bjtop leaderboard (stops a lucky 1-game 100% from topping
    the list).""")))

conf.registerGlobalValue(BlackJack, 'commandThrottle',
    registry.Integer(2, _("""Minimum seconds between two blackjack commands
    from the same nick in the same channel (anti-spam, silent).""")))

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
