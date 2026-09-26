"""Racing-center rivals: each region's story and its ten racers, weakest to champion.

Each rival gets one line of dialogue before their race. Race k's rival is rated
RIVAL_RATINGS[k] and calibrated to its generated track so a flawless driver rated 10 lower
just wins. The ladder climbs gently through race 6, then steeply for the last four: the
champion (350) needs rating 340, level 25.
"""

from __future__ import annotations



RACES_PER_CENTER = 10
LAPS = 3
RIVAL_RATINGS = (100, 110, 120, 140, 150, 170, 220, 260, 300, 350)

STORIES = {
    "city": "Sunside's night crews race the old harbor loop for the Neon Crown.",
    "jungle": "Expedition drivers race the ruin roads before the rains wash them out.",
    "desert": "Caravan clans settle every feud on the sand at the Mirage Cup.",
    "snow": "On the frozen pass, only the Ice Syndicate decides who drives.",
    "rural": "Every harvest, the county's farm families race for the Golden Plough.",
}

# (name, dialogue line, car sprite). Lines stay short enough for the offer panel.
RIVALS = {
    "city": (
        ("Dash Moreno", "New plates? Try to keep up, rookie.", "racer_cyan"),
        ("Pixie Lang", "I tune engines by ear. Yours sounds scared.", "racer_yellow"),
        ("Vince Carter", "The Neon Crown doesn't hand out pity laps.", "racer_blue"),
        ("Mara Quill", "I've mapped every pothole in Sunside.", "racer_purple"),
        ("Rook Adeyemi", "Harbor loop's mine after midnight.", "racer_black"),
        ("Sasha Vale", "My sponsors are watching. Don't embarrass me.", "racer_orange"),
        ("Jett Okafor", "You're fast. I'm faster. Simple math.", "racer_lime"),
        ("Nina Stroud", "Three crews tried to take my spot. Gone.", "racer_cyan"),
        ("Kaito Reyes", "Beat me and the Crown takes notice.", "racer_purple"),
        ("Queen Lux", "The Neon Crown is mine. Come take it.", "racer_black"),
    ),
    "jungle": (
        ("Pip Marlow", "Mind the roots! They bite.", "racer_lime"),
        ("Tomas Reed", "I race the ruins before the rains come.", "racer_orange"),
        ("Ada Nkemelu", "The jungle eats slow drivers.", "racer_cyan"),
        ("Bram Holt", "My maps are older than your car.", "racer_yellow"),
        ("Lina Sato", "Heard you drive clean. Mud says otherwise.", "racer_blue"),
        ("Ezra Fenn", "Temple gate's ahead. Don't blink.", "racer_purple"),
        ("Nova Ruiz", "Monkeys cheer for me, you know.", "racer_lime"),
        ("Grey Okoro", "Twenty seasons on these trails. Your turn.", "racer_black"),
        ("Isla Voss", "The expedition picks one driver. Me.", "racer_orange"),
        ("The Warden", "Nobody crosses the old ruins without my nod.", "racer_black"),
    ),
    "desert": (
        ("Sami Dune", "Sand in your eyes already?", "racer_yellow"),
        ("Rhea Kassim", "The caravan chose me to test you.", "racer_orange"),
        ("Omar Tells", "Heat mirages won't save you.", "racer_cyan"),
        ("Zara Fen", "My clan's feud ends on this sand.", "racer_purple"),
        ("Kade Sol", "I drove here before the roads were roads.", "racer_blue"),
        ("Nia Ashford", "Dunes shift. My lines don't.", "racer_lime"),
        ("Tariq Vane", "Win and the clans will sing of you.", "racer_black"),
        ("Leila Storm", "Sandstorm's coming. So am I.", "racer_orange"),
        ("Hadi Rook", "The Mirage Cup is almost in your hands. Almost.", "racer_yellow"),
        ("Sultan Rae", "Every clan bows at the Mirage Cup. Will you?", "racer_black"),
    ),
    "snow": (
        ("Fin Frost", "Ice rule one: don't brake in the turn.", "racer_blue"),
        ("Kova Lind", "The pass doesn't forgive. Neither do I.", "racer_cyan"),
        ("Oskar Berg", "Studded tires? Cute.", "racer_black"),
        ("Tove Ask", "My hands stay warm on the wheel. Yours?", "racer_purple"),
        ("Ivan Petrov", "The Syndicate sent me to cool you down.", "racer_blue"),
        ("Lumi Hale", "Snowblind drivers end up in the drifts.", "racer_lime"),
        ("Rune Solberg", "I've slid this pass sideways for a decade.", "racer_orange"),
        ("Astrid Kell", "The Syndicate's inner circle is watching.", "racer_cyan"),
        ("Magnus Ice", "One more win and you meet the boss.", "racer_black"),
        ("The Glacier", "The Ice Syndicate answers to me. Prove you don't.", "racer_blue"),
    ),
    "rural": (
        ("Billy Harlan", "Pa says I can't lose to city folk.", "racer_orange"),
        ("Dot Whitfield", "Fresh eggs for the winner! Not you.", "racer_yellow"),
        ("Cal Brody", "This mud's older than both of us.", "racer_lime"),
        ("Ma Jessop", "I've been racing since before tractors had cabs.", "racer_purple"),
        ("Luke Tanner", "The Tanners haven't lost a harvest race in years.", "racer_blue"),
        ("June Amberly", "Pretty car. Shame about the mud.", "racer_cyan"),
        ("Hank Ostrow", "Win this and the county knows your name.", "racer_black"),
        ("Rosa Delgado", "My family's farm rides on this race.", "racer_orange"),
        ("Old Silas", "I taught half this county to drive. Not you.", "racer_yellow"),
        ("Big Mae", "The Golden Plough stays on my porch, kid.", "racer_black"),
    ),
}


def track_size(race: int) -> int:
    """Blob cells for race 1-10's generated track: 4 (short, few corners) up to 12."""
    return 4 + race * 8 // 10


def rival(region: str, race: int):
    """(name, line, sprite) of the racer faced in race 1-10."""
    return RIVALS[region][race - 1]
