import json
import random
from pathlib import Path

from i18n import t, tt

_agents: list[dict] = []


def load_agents() -> list[dict]:
    global _agents
    if not _agents:
        path = Path(__file__).parent / "data" / "agents.json"
        with open(path, encoding="utf-8") as f:
            _agents = json.load(f)
    return _agents


def random_agent() -> dict:
    return random.choice(load_agents())


def format_agent(agent: dict, lang: str = "en") -> str:
    name = agent.get(f"name_{lang}", agent["name"]) if lang != "en" else agent["name"]

    role_emoji = {
        "Duelist": "🔴",
        "Initiator": "🟡",
        "Controller": "🟣",
        "Sentinel": "🟢",
    }.get(agent["role"], "")

    role = tt("role", agent["role"], lang)

    return f"{role_emoji} *{name}*\n{role}"
