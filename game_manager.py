import random
import string
from dataclasses import dataclass, field


@dataclass
class Room:
    code: str
    host_id: int
    chat_id: int
    message_id: int
    players: list[int] = field(default_factory=list)
    player_names: dict[int, str] = field(default_factory=dict)
    state: str = "waiting"   # waiting | playing | ended
    card: dict | None = None
    spy_id: int | None = None
    lang: str = "en"
    mode: str = "cr"         # "cr" | "dota"


rooms: dict[str, Room] = {}
# map chat_id -> room code for quick lookup
chat_rooms: dict[int, str] = {}


def _generate_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code


def create_room(host_id: int, chat_id: int, message_id: int, host_name: str, lang: str = "en", mode: str = "cr") -> Room:
    if chat_id in chat_rooms:
        old_code = chat_rooms[chat_id]
        rooms.pop(old_code, None)

    code = _generate_code()
    room = Room(
        code=code,
        host_id=host_id,
        chat_id=chat_id,
        message_id=message_id,
        players=[host_id],
        player_names={host_id: host_name},
        lang=lang,
        mode=mode,
    )
    rooms[code] = room
    chat_rooms[chat_id] = code
    return room


def get_room_by_chat(chat_id: int) -> Room | None:
    code = chat_rooms.get(chat_id)
    return rooms.get(code) if code else None


def add_player(room: Room, user_id: int, user_name: str) -> bool:
    if user_id in room.players:
        return False
    room.players.append(user_id)
    room.player_names[user_id] = user_name
    return True


def start_game(room: Room, card: dict) -> int:
    room.card = card
    room.spy_id = random.choice(room.players)
    room.state = "playing"
    return room.spy_id


def end_game(room: Room) -> None:
    room.state = "ended"
    chat_rooms.pop(room.chat_id, None)
    rooms.pop(room.code, None)


def player_list_text(room: Room, none_text: str = "_(none yet)_") -> str:
    lines = [f"👤 {name}" for name in room.player_names.values()]
    return "\n".join(lines) if lines else none_text
