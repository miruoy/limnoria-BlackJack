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

### BlackJack — plugin entry point

import supybot

from . import plugin
from . import config
from . import game
from importlib import reload
reload(plugin)  # In case we're being reloaded.
reload(game)    # our own module, reload with the plugin

__version__ = '1.0.0'
__author__ = supybot.Author(name='Youri Matthys', nick='miruoy',
                            email='2657774+miruoy@users.noreply.github.com')
__contributors__ = {}
__url__ = 'https://github.com/miruoy/limnoria-BlackJack'

Class = plugin.Class
