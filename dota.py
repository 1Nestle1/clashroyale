import json
import random
from pathlib import Path

from i18n import t, tt

_heroes: list[dict] = []


def load_heroes() -> list[dict]:
    global _heroes
    if not _heroes:
        path = Path(__file__).parent / "data" / "heroes.json"
        with open(path, encoding="utf-8") as f:
            _heroes = json.load(f)
    return _heroes


def random_hero() -> dict:
    return random.choice(load_heroes())


def format_hero(hero: dict, lang: str = "en") -> str:
    name = hero.get(f"name_{lang}", hero["name"]) if lang != "en" else hero["name"]

    attr_emoji = {
        "Strength": "🟥",
        "Agility": "🟩",
        "Intelligence": "🟦",
        "Universal": "🟪",
    }.get(hero["attribute"], "")
    attack_emoji = {"Melee": "⚔️", "Ranged": "🏹"}.get(hero["attack"], "")

    attribute = tt("attribute", hero["attribute"], lang)
    attack = tt("attack", hero["attack"], lang)

    return (
        f"{attr_emoji} *{name}*\n"
        f"{attack_emoji} {attribute} · {attack}"
    )
