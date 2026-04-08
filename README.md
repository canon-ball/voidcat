# VOIDCAT

[![CI](https://github.com/canon-ball/voidcat/actions/workflows/ci.yml/badge.svg)](https://github.com/canon-ball/voidcat/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/canon-ball/voidcat/graph/badge.svg)](https://codecov.io/gh/canon-ball/voidcat)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-2ea44f.svg)](LICENSE)

You are not the hero. You are the ship's last cat.

`VOIDCAT` is a graphical stealth roguelite built with Python and `pygame-ce`. It runs as a full GUI game window with pixel-art map rendering, a tactical HUD, codex panels, threat overlays, and animated feedback instead of a plain terminal display. You prowl a dying ship, restore relays, bait patrols with noise, and decide whether to cash out safely or push deeper into the dark for a better run.

It is designed around readable tactical stealth:

- turn-based movement with fast runs and high tension
- enemy intent telegraphs and a toggleable threat view
- daily runs, seeded runs, and strong end-of-run summaries
- deck conditions that change the feel of each floor
- dock upgrades that push distinct Stealth, Mobility, and Scavenger routes
- a full-screen codex that explains the systems without breaking the mood

## Why It Stands Out

- **Cat-first stealth fantasy**: this is not a soldier game, a dungeon crawler, or a combat roguelike. You are small, fast, disruptive, and always a little outmatched.
- **Readable pressure**: patrol intent lines, map markers, threat zones, alert stages, and deck conditions tell you why a floor feels dangerous.
- **Memorable runs**: daily seeds, build routes, deck histories, highlights, and share-ready end cards make runs feel like stories instead of score dumps.
- **Short, sharp decisions**: hiss, hide, knock, pounce, wait, and route planning all matter. The game rewards information and timing over brute force.

## Features

- **Graphical command-deck presentation**
  - pixel-art map rendering
  - layered HUD with power, noise, alert, deck condition, and build route
  - full-screen help/codex and score panels
- **Stealth toolkit**
  - `Hiss` to break close pressure
  - `Hide` to cool noise and shake pursuit
  - `Knock` to plant a decoy down a lane
  - `Pounce` to burst across space or steal loot
- **Run variety**
  - `Training Deck`, `Low Light`, `Hot Deck`, and `Signal Surge` floors
  - daily run mode and rerollable personal seeds
  - distinct dock-offer archetypes: Stealth, Mobility, Scavenger
- **Run summary and meta flavor**
  - run highlights
  - deck condition history
  - build path summary
  - share line on the end card

## Gameplay Loop

1. Enter the floor through the dock.
2. Restore every relay.
3. Return to the dock.
4. Spend scrap on one dock offer if you want.
5. Descend for another floor or extract safely.

The deeper you go, the more the ship turns against you.

## Install

### Quick Run From A Checkout

This is the most reliable path if you are playing straight from source:

```bash
git clone https://github.com/canon-ball/voidcat.git
cd voidcat
python3 -m pip install .
python3 -m voidcat
```

### Launching The Graphical GUI

The graphical build is the main version of the game.

Use one of these launch methods:

```bash
voidcat
```

```bash
python3 -m voidcat
```

If you have an older local install, you may also still have:

```bash
voidcat-gfx
```

`voidcat-gfx` launches the same graphical GUI, but `voidcat` is the current primary launcher in this repository.

### Editable Install For Development

```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[dev]'
voidcat
```

If your local `pip` is older and editable install support is incomplete, this fallback still runs the game directly from source:

```bash
PYTHONPATH=src python3 -m voidcat
```

## Controls

| Key | Action |
| --- | --- |
| `W A S D` | Move |
| `Space` | Wait and listen for a turn |
| `E` | Interact with relay, dock, or signal |
| `H` | Hiss to scare adjacent crawlers and mimics |
| `X` | Hide to cool noise and reduce pressure |
| `K` | Aim a knock and throw a decoy |
| `P` | Aim a pounce and leap 1-2 tiles |
| `V` | Toggle tactical threat view |
| `1 2 3` | Buy one dock offer |
| `?` | Open the codex |
| `Q` | Quit |
| Title: `D` | Start the daily run |
| Title: `R` | Reroll a personal seed |

## Enemies

- **Crawler**: sound-hunter that commits hard to noise and decoys.
- **Stalker**: line-of-sight predator that punishes open mistakes.
- **Mimic**: fake loot until it springs.

## Development

The repository ships with:

- GitHub Actions CI
- `ruff` linting
- `mypy` type checking
- `coverage.py` reporting
- `unittest` and property-style tests
- a 95% coverage gate

Useful local commands:

```bash
PYTHONPATH=src python3 -m ruff check src tests
PYTHONPATH=src python3 -m mypy src/voidcat
PYTHONPATH=src python3 -m unittest discover -s tests -q
PYTHONPATH=src python3 -m coverage run -m unittest discover -s tests -q
PYTHONPATH=src python3 -m coverage report
```

Current local verification baseline:

- 92 tests passing
- 95% total coverage

## Project Structure

```text
src/voidcat/
  engine.py        # game facade and shared state
  gameplay.py      # turn logic and stealth rules
  progression.py   # floor starts, dock offers, signal outcomes
  presentation.py  # render-state assembly for the UI
  gfx_app.py       # pygame frontend
  models.py        # domain and render models

tests/
  test_engine.py
  test_presentation.py
  test_gfx_app.py
  ...
```

## Roadmap Direction

The current direction is to push `VOIDCAT` further into:

- stronger run identity
- clearer tactical readability
- more memorable floor events
- richer daily-run and community-sharing features

## License

MIT. See [LICENSE](LICENSE).
