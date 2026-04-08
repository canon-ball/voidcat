# VOIDCAT

You are not the hero. You are the ship's last cat.

`VOIDCAT` is a Python stealth roguelite built around a `pygame-ce` command-deck presentation.
It keeps the shared turn-based stealth rules, but the flagship experience is now the graphical build: pixel-art sprites, enemy intent telegraphs, objective markers, floor conditions, daily seeds, and a full-screen codex.

## Run

```bash
python3 -m pip install -e .
voidcat
```

## Controls

- `w a s d`: move
- `e`: interact with relays, dock, and signals
- `h`: hiss to scare adjacent crawlers and mimics
- `x`: hide to suppress noise, lower alert, and shake distant stalkers
- `k`: knock, then choose a direction to create a strong decoy
- `p`: pounce, then choose a direction
- `v`: toggle threat view to see projected pressure zones
- `1 2 3`: buy a dock offer after extraction
- `?`: open the in-game rules codex
- `q`: quit
- title screen: `d` starts the daily run, `r` rerolls the current seed

## How To Play

- Restore every relay on the current floor.
- Return to the dock once the relays are active.
- Spend scrap on one dock upgrade if you want, then descend or end the run safely.
- Keep an eye on power, noise, ship alert, floor condition, build path, and threat view. The current build teaches floor one more gently, then escalates through low-light decks, hot decks, and signal-surge decks.
- `Knock` pulls enemies toward a decoy point deeper in the corridor.
- `Hide` now lasts longer and is the main way to cool a bad stealth situation.
- `D` on the title screen starts the shared daily run. `R` rerolls a personal seed until you like the route.
- Dock offers now push clearer Stealth, Mobility, and Scavenger routes instead of feeling interchangeable.
- `?` opens a full codex screen that explains the controls, run loop, stealth systems, and enemy behavior without the live map showing through.

## Enemy Notes

- `Crawler`: rounded sound-hunter that commits hard to noise and decoys.
- `Stalker`: sharper hunter that sees farther and escalates faster.
- `Mimic`: a fake battery until it springs the trap.
