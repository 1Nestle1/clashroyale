import json
import random
from pathlib import Path

from i18n import t, tt

_cards: list[dict] = []


def load_cards() -> list[dict]:
    global _cards
    if not _cards:
        path = Path(__file__).parent / "data" / "cards.json"
        with open(path, encoding="utf-8") as f:
            _cards = json.load(f)
    return _cards


def random_card() -> dict:
    return random.choice(load_cards())


def format_card(card: dict, lang: str = "en") -> str:
    name = card.get(f"name_{lang}", card["name"]) if lang != "en" else card["name"]
    desc = card.get(f"description_{lang}", card["description"]) if lang != "en" else card["description"]

    rarity_emoji = {"Common": "⚪", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟡"}.get(card["rarity"], "")
    type_emoji = {"Troop": "⚔️", "Spell": "✨", "Building": "🏰"}.get(card["type"], "")

    rarity = tt("rarity", card["rarity"], lang)
    ctype = tt("type", card["type"], lang)
    elixir_word = t("elixir", lang)

    return (
        f"{rarity_emoji} *{name}*\n"
        f"{type_emoji} {ctype} · {rarity} · {card['elixir']} {elixir_word}\n\n"
        f"_{desc}_"
    )
