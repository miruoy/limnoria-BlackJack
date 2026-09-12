# BlackJack

A multiplayer blackjack table for [Limnoria](https://github.com/ProgVal/Limnoria).
One player opens a table, others join, and everyone plays against the dealer.
Split, double down, a move timer, anti-spam and a win-rate leaderboard.

No third-party dependencies — pure Python standard library.

> **Command prefix:** examples below use `@`, because that is the prefix on
> the bot this was written for. The plugin itself is prefix-agnostic: whatever
> prefix your bot uses (`!`, `.`, `@`, …) works.

## Commands

| Command | What it does |
| --- | --- |
| `@bj` | Opens a table in the channel. You are seated first; others get 60s to join. One table per channel. |
| `@bjjoin` | Takes a seat at an open table. Join order = play order. |
| `@deal` | (Table opener only) Deals immediately instead of waiting for the join window. |
| `@hit` | Draws another card. |
| `@stand` | Ends your turn on the current hand. |
| `@split` | Splits a matching pair into two hands (single split only). |
| `@double` | Doubles down: one more card, then that hand is done. |
| `@bjstats [nick]` | Shows your stats, or another player's. |
| `@bjtop` | Leaderboard by win rate (players with enough hands). |

## How a round plays

1. `@bj` opens the table (60s join window, or `@deal` to start now).
2. Cards are dealt to every player and to the dealer (one card face down).
3. Players act in join order. Each player plays their hand(s) fully — after a
   split that means hand 1, then hand 2 — before the next player.
4. The dealer plays once at the end, against everyone.
5. Results per player, then the stats/leaderboard are updated.

## Card notation

Cards are written as words so they are readable in any IRC client or terminal
(no Unicode suit glyphs, no ANSI colour):

```
Dealer shows: 9 of Clubs, ??
You: 8 of Spades, 8 of Hearts  = 16
Your move? [ hit | stand | split | double ]
```

## Rules implemented

- Aces count as 11 unless that busts, then 1.
- Dealer stands on all 17s (including soft 17).
- Natural blackjack (21 on the first two cards) wins immediately and the
  dealer does not play for that player.
- A 21 made **after a split** is *not* a blackjack — it just counts as 21.
- Single split only: a player can never hold more than two hands (no re-split).
- Split aces draw one card each and get no further hits.
- Push (equal totals) neither wins nor loses.
- Every hand counts separately, so a split adds two hands to your stats.

## Anti-spam

- One table per channel.
- Only the player whose turn it is may act; other players' `@hit`/`@stand`/
  etc. are silently ignored (so they cannot flood the channel).
- Per-nick command throttle (default 2s), silent.
- 120s cooldown before a new table can be opened in the same channel after a
  game ends.
- The bot's own global flood protection still applies on top.

## Move timer

Each turn has a timeout (default 15s). If you do not act, the bot auto-stands
for you with a sharp comment, and the hand counts normally. A warning appears
a few seconds before the deadline.

## Configuration

All values live under `plugins.BlackJack.*` and are **global** (set them with
`config plugins.BlackJack.moveTimeout 20`).

| Value | Default | Meaning |
| --- | --- | --- |
| `moveTimeout` | `15` | Seconds per move before auto-stand. |
| `joinTimeout` | `60` | Seconds the join window stays open. |
| `gameCooldown` | `120` | Seconds before a new table in the same channel after a game. |
| `maxPlayers` | `6` | Maximum players at one table. |
| `minHandsForTop` | `15` | Minimum hands played to appear in `@bjtop`. |
| `commandThrottle` | `2` | Seconds between two commands from the same nick (silent). |

## Installation

### Via git (copy into your plugins directory)

```
cp -r BlackJack /path/to/your/bot/plugins/
rm -rf /path/to/your/bot/plugins/BlackJack/__pycache__
# in the bot: load BlackJack
```

### Via pip (from the git repo)

```
pip3 install git+https://github.com/miruoy/limnoria-BlackJack.git
# then in the bot: load BlackJack
```

### Via PluginDownloader (once the repo is in Limnoria's list)

```
@plugindownloader install miruoy
```

## Leaderboard storage

Stats are kept per bot in `scores.json` next to `plugin.py` (git-ignored).
It survives restarts. Delete it to reset the leaderboard.

## Tests

The blackjack engine (`game.py`) is deliberately free of Limnoria imports so
it can be tested standalone:

```
python3 test_game.py     # 13 rule cases + 2000 fuzz games
```

`test.py` is the standard Limnoria `PluginTestCase` and runs under the bot's
test runner.

## License

GPL-2.0. See `LICENSE`.
