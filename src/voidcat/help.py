from __future__ import annotations

from .models import OverlayState

HELP_PAGES = [
    [
        "VOIDCAT // CONTROLS",
        "",
        "W A S D  move",
        "Space    wait and listen for a turn",
        "E        interact with relay, dock, or signal",
        "H        hiss to scare adjacent crawlers and mimics",
        "X        hide to cool noise, drop alert, and break distant chase",
        "K        knock, then choose a direction to throw a decoy",
        "P        pounce, then choose a direction to leap 1-2 tiles",
        "V        toggle the tactical threat overlay",
        "1 2 3    buy a dock offer after extraction",
        "F11      toggle fullscreen in the graphical build",
        "?        open or close this codex",
        "Q        quit the current session",
        "",
        "Title:   N starts a seeded run, D starts the daily run, R rerolls your seed",
    ],
    [
        "VOIDCAT // HOW A RUN WORKS",
        "",
        "Restore every relay on the floor.",
        "Return to the dock once the relays are active.",
        "Spend scrap on one dock upgrade if you want.",
        "Each new floor starts with a fresh power refill.",
        "Overcharge cells raise that refill cap for the rest of the run.",
        "Descend for another floor or end the run safely.",
        "",
        "Score comes from relays, scrap, extraction bonus, and rare tech.",
    ],
    [
        "VOIDCAT // HISS AND HIDE",
        "",
        "Hiss: costs 1 power, makes 2 noise, and triggers a 5-turn cooldown.",
        "It only affects adjacent crawlers and mimics.",
        "Use hiss when something is already on top of you.",
        "Hide: costs 1 power, drops noise, trims alert, and starts hidden turns.",
        "Hide only shakes stalkers after you break sightlines and if they are not adjacent.",
        "Best use: round a corner, hide, then rotate while they investigate old noise.",
    ],
    [
        "VOIDCAT // KNOCK AND POUNCE",
        "",
        "Knock: costs 1 power, adds 5 noise, and throws a decoy down a corridor.",
        "That decoy stays live for two enemy phases and pulls patrols off your line.",
        "Use knock before crossing an exposed lane or touching a relay in open space.",
        "Pounce: leaps 1-2 tiles, costs 2 power, adds 2 noise, and has a 4-turn cooldown.",
        "Use it to grab loot, skip a hot tile, or break a chokepoint quickly.",
        "Do not pounce blind into enemies or heat unless the trade is worth it.",
    ],
    [
        "VOIDCAT // STEALTH SYSTEMS",
        "",
        "Power is your life support. If it hits zero, the run ends.",
        "Noise draws enemies and raises ship alert.",
        "Ship alert climbs from CALM to HUNT to SWEEP as the run gets louder.",
        "Heat tiles cost extra power unless you insulate your paws.",
        "Signals are gambles: supplies, modules, or an ambush with extra noise.",
        "Space-wait when you need to bleed noise, watch patrols, or let cooldowns advance.",
    ],
    [
        "VOIDCAT // ENEMIES AND TACTICS",
        "",
        "Crawler: rounded hunter that commits hard to sound and decoys.",
        "Stalker: taller hunter that sees farther and escalates faster.",
        "Mimic: a fake battery until it springs the trap.",
        "",
        "Knock first when you need to cross space a crawler can hear.",
        "Hide after breaking line of sight to make a stalker search the wrong lane.",
        "Hiss is a panic tool, not a scouting tool.",
        "Pounce is strongest as a burst reposition, not an every-turn move.",
    ],
]


def help_overlay(page_index: int) -> OverlayState:
    total = len(HELP_PAGES)
    page = HELP_PAGES[page_index % total]
    return OverlayState(
        title=page[0],
        lines=list(page[1:])
        + ["", f"Page {page_index % total + 1}/{total}  Left/Right or Tab to switch  Esc closes"],
        backdrop=True,
    )
