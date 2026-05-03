import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

import game_manager as gm
from cards import format_card, random_card
from dota import format_hero, random_hero
from valorant import format_agent, random_agent
from i18n import detect_lang, t

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ROOT = Path(__file__).parent
ASSETS = {
    "cr": ROOT / "Assets 2026-04-27",
    "dota": ROOT / "dota_assets",
    "valorant": ROOT / "valorant_assets",
}


# ---------- helpers ----------

def _image_path(mode: str, item: dict) -> Path | None:
    name = item.get("image")
    if not name:
        return None
    p = ASSETS[mode] / name
    return p if p.exists() else None


def _user_name(user) -> str:
    return user.full_name or user.username or str(user.id)


def _pick_subject(mode: str) -> dict:
    if mode == "dota":
        return random_hero()
    if mode == "valorant":
        return random_agent()
    return random_card()


def _format_subject(mode: str, item: dict, lang: str) -> str:
    if mode == "dota":
        return format_hero(item, lang)
    if mode == "valorant":
        return format_agent(item, lang)
    return format_card(item, lang)


def _key(mode: str, base: str) -> str:
    """Mode-specific i18n key, e.g. _key('dota', 'spy_msg') -> 'spy_msg_dota'."""
    return f"{base}_{mode}"


# ---------- keyboards ----------

def _mode_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("mode_cr", lang), callback_data="mode:cr")],
        [InlineKeyboardButton(t("mode_dota", lang), callback_data="mode:dota")],
        [InlineKeyboardButton(t("mode_valorant", lang), callback_data="mode:valorant")],
    ])


def _join_keyboard(code: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t("btn_join", lang), callback_data=f"join:{code}")],
        [InlineKeyboardButton(t("btn_start", lang), callback_data=f"start:{code}")],
        [InlineKeyboardButton(t("btn_cancel", lang), callback_data=f"cancel:{code}")],
    ])


def _lobby_text(room: gm.Room) -> str:
    return t(
        _key(room.mode, "lobby"),
        room.lang,
        code=room.code,
        count=len(room.players),
        players=gm.player_list_text(room, t("none_yet", room.lang)),
    )


# ---------- handlers ----------

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_chat.type == "private":
        lang = detect_lang(update.effective_user)
        await update.message.reply_text(t("welcome", lang), parse_mode=ParseMode.MARKDOWN)


async def cmd_newgame(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    user = update.effective_user
    lang = detect_lang(user)

    if chat.type == "private":
        await update.message.reply_text(t("use_in_group", lang))
        return

    # Show mode picker. The host_id is encoded in the callback so only they can pick.
    await update.message.reply_text(
        t("pick_mode", lang),
        reply_markup=_mode_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    mode = query.data.split(":")[1]
    if mode not in ("cr", "dota", "valorant"):
        await query.answer()
        return

    user = query.from_user
    lang = detect_lang(user)
    chat_id = query.message.chat_id
    msg_id = query.message.message_id

    # Reuse the picker message as the lobby message.
    room = gm.create_room(
        host_id=user.id,
        chat_id=chat_id,
        message_id=msg_id,
        host_name=_user_name(user),
        lang=lang,
        mode=mode,
    )

    await query.answer()
    await query.edit_message_text(
        _lobby_text(room),
        reply_markup=_join_keyboard(room.code, lang),
        parse_mode=ParseMode.MARKDOWN,
    )


async def cb_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    code = query.data.split(":")[1]
    room = gm.rooms.get(code)

    if not room or room.state != "waiting":
        await query.answer(t("room_closed", room.lang if room else "en"), show_alert=True)
        return

    user = query.from_user
    added = gm.add_player(room, user.id, _user_name(user))

    if not added:
        await query.answer(t("already_joined", room.lang), show_alert=True)
        return

    await query.answer()
    await query.edit_message_text(
        _lobby_text(room),
        reply_markup=_join_keyboard(code, room.lang),
        parse_mode=ParseMode.MARKDOWN,
    )

    # Privately notify the host that a new player joined.
    if user.id != room.host_id:
        try:
            await context.bot.send_message(
                room.host_id,
                t("join_notif", room.lang, name=_user_name(user)),
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception:
            log.info("Could not DM host %s about join (probably hasn't /start'd the bot)", room.host_id)


async def cb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    code = query.data.split(":")[1]
    room = gm.rooms.get(code)

    if not room or room.state != "waiting":
        await query.answer(t("room_closed", room.lang if room else "en"), show_alert=True)
        return

    lang = room.lang
    if query.from_user.id != room.host_id:
        await query.answer(t("cancel_denied", lang), show_alert=True)
        return

    gm.end_game(room)  # cleans up the room
    await query.answer()
    await query.edit_message_text(t("game_cancelled", lang), parse_mode=ParseMode.MARKDOWN)


async def cb_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    code = query.data.split(":")[1]
    room = gm.rooms.get(code)

    if not room:
        await query.answer(t("room_not_found", "en"), show_alert=True)
        return
    lang = room.lang
    if room.state != "waiting":
        await query.answer(t("already_started", lang), show_alert=True)
        return
    if query.from_user.id != room.host_id:
        await query.answer(t("host_only", lang), show_alert=True)
        return
    if len(room.players) < 2:
        await query.answer(t("need_players", lang), show_alert=True)
        return

    await query.answer()

    subject = _pick_subject(room.mode)
    spy_id = gm.start_game(room, subject)

    failed: list[str] = []
    for uid in room.players:
        name = room.player_names[uid]
        try:
            if uid == spy_id:
                await context.bot.send_message(
                    uid, t(_key(room.mode, "spy_msg"), lang), parse_mode=ParseMode.MARKDOWN
                )
            else:
                msg = t(
                    _key(room.mode, "villager_msg"),
                    lang,
                    subject=_format_subject(room.mode, subject, lang),
                )
                img_path = _image_path(room.mode, subject)
                if img_path:
                    with img_path.open("rb") as f:
                        await context.bot.send_photo(uid, f, caption=msg, parse_mode=ParseMode.MARKDOWN)
                else:
                    await context.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            log.exception("Failed to DM user %s", uid)
            failed.append(name)

    status = t("game_started", lang, count=len(room.players))
    if failed:
        bot_username = (await context.bot.get_me()).username
        status += t("dm_failed", lang, names=", ".join(failed), bot=bot_username)

    await query.edit_message_text(status, parse_mode=ParseMode.MARKDOWN)


async def cmd_reveal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    room = gm.get_room_by_chat(chat.id)
    user_lang = detect_lang(update.effective_user)

    if not room or room.state != "playing":
        await update.message.reply_text(t("no_game", user_lang))
        return

    text = t(
        _key(room.mode, "reveal"),
        room.lang,
        spy=room.player_names[room.spy_id],
        subject=_format_subject(room.mode, room.card, room.lang),
    )
    img_path = _image_path(room.mode, room.card)
    gm.end_game(room)
    if img_path:
        with img_path.open("rb") as f:
            await update.message.reply_photo(f, caption=text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN not set. Copy .env.example to .env and fill in your token.")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("newgame", cmd_newgame))
    app.add_handler(CommandHandler("reveal", cmd_reveal))
    app.add_handler(CallbackQueryHandler(cb_mode, pattern=r"^mode:"))
    app.add_handler(CallbackQueryHandler(cb_join, pattern=r"^join:"))
    app.add_handler(CallbackQueryHandler(cb_start, pattern=r"^start:"))
    app.add_handler(CallbackQueryHandler(cb_cancel, pattern=r"^cancel:"))

    log.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
