
import asyncio
from functools import wraps

from pyrogram import Client, filters
from pyrogram.errors import RPCError

from .config import BOT_TOKEN, API_ID, API_HASH, ADMIN_ID, MAX_BOTS
from .db import (
    init_db,
    add_destination,
    remove_destination,
    list_destinations
)
from . import user_session
from .user_session import (
    start_saved_user,
    login_with_string,
    begin_phone_login,
    finish_phone_login,
    logout_user
)
from .broadcast import broadcaster


bot = Client(
    "abbot_controller",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

pending = {}
last_post = {}

capture_client = None


def is_admin(message):
    return bool(
        message.from_user
        and message.from_user.id == ADMIN_ID
    )


def admin_only(func):
    @wraps(func)
    async def wrapper(client, message):
        if not is_admin(message):
            return
        return await func(client, message)
    return wrapper


async def reply(message, text):
    await message.reply_text(
        text,
        disable_web_page_preview=True
    )


async def status_sender(text):
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        pass


def register_user_handler(client):
    global capture_client

    if capture_client is client:
        return

    broadcaster.capture_reply(
        client,
        bot.me.id,
        status_sender
    )

    capture_client = client


@bot.on_message(filters.private & filters.command("start"))
@admin_only
async def start(_, message):
    me = user_session.user_client
    bots = await list_destinations()

    await reply(
        message,
        "🤖 **ABBot Multi-Bot Broadcaster**\n\n"
        f"User account: {'Connected' if me else 'Not connected'}\n"
        f"Destination bots: {len(bots)}/{MAX_BOTS}\n\n"
        "**Login:** `/login`, `/string`, `/LoginDetails`, `/Logout`\n"
        "**Bot list:** `/AddBots`, `/RemoveBots`, `/ListBots`\n"
        "**Broadcast:** Forward a post here, then `/SendAll`\n"
        "**Control:** `/Cancel`"
    )


@bot.on_message(filters.private & filters.command("login"))
@admin_only
async def login(_, message):
    old = pending.pop(ADMIN_ID, None)

    if old and old.get("client"):
        try:
            await old["client"].disconnect()
        except Exception:
            pass

    pending[ADMIN_ID] = {"step": "phone"}

    await reply(
        message,
        "Send your phone number in international format.\n"
        "Example: +91XXXXXXXXXX"
    )


@bot.on_message(filters.private & filters.command("string"))
@admin_only
async def string_login(_, message):
    pending[ADMIN_ID] = {"step": "session_string"}

    await reply(
        message,
        "Send your Pyrogram session string.\n"
        "It will be stored in the configured session storage.\n"
        "Never share this string with anyone."
    )


@bot.on_message(
    filters.private
    & filters.command(["logindetails"])
)
@admin_only
async def login_details(_, message):
    client = user_session.user_client

    if not client:
        return await reply(
            message,
            "No user account is connected."
        )

    me = await client.get_me()

    await reply(
        message,
        "**Connected User Account**\n"
        f"Name: {me.first_name or '-'}\n"
        f"Username: @{me.username or '-'}\n"
        f"User ID: `{me.id}`\n"
        f"Phone: `{me.phone_number or 'Hidden by Telegram'}`\n"
        "Session: Protected (not displayed)"
    )


@bot.on_message(filters.private & filters.command("logout"))
@admin_only
async def logout(_, message):
    global capture_client

    await logout_user()
    capture_client = None

    pending.pop(ADMIN_ID, None)

    await reply(
        message,
        "User account logged out and saved session removed."
    )


@bot.on_message(filters.private & filters.command("addbots"))
@admin_only
async def addbots(_, message):
    pending[ADMIN_ID] = {"step": "add_bot"}

    await reply(
        message,
        "Send the destination bot username.\n"
        "Example: @ExampleBot"
    )


@bot.on_message(filters.private & filters.command("removebots"))
@admin_only
async def removebots(_, message):
    pending[ADMIN_ID] = {"step": "remove_bot"}

    await reply(
        message,
        "Send the username of the destination bot to remove."
    )


@bot.on_message(filters.private & filters.command("listbots"))
@admin_only
async def listbots(_, message):
    rows = await list_destinations()

    if not rows:
        return await reply(
            message,
            "No destination bots saved."
        )

    lines = [
        f"**Saved destination bots ({len(rows)}/{MAX_BOTS})**"
    ]

    lines.extend(
        f"{i}. {name} — @{username} (`{bot_id}`)"
        for i, (bot_id, username, name)
        in enumerate(rows, 1)
    )

    await reply(message, "\n".join(lines))


@bot.on_message(filters.private & filters.command("sendall"))
@admin_only
async def sendall(_, message):
    client = user_session.user_client
    source = last_post.get(ADMIN_ID)

    if not client:
        return await reply(
            message,
            "Connect the User Account first using /login or /string."
        )

    if not source:
        return await reply(
            message,
            "Forward or send a post to ABBot first, then use /SendAll."
        )

    if broadcaster.running:
        return await reply(
            message,
            "A broadcast is already running."
        )

    if pending.get(ADMIN_ID):
        return await reply(
            message,
            "Finish or cancel the current operation first."
        )

    register_user_handler(client)

    status = await message.reply_text(
        "Delivering post to the logged-in User Account..."
    )

    try:
        # The user account receives this in its private chat with ABBot.
        # The destination is the controller bot's ID, NOT the user's own ID.
        controller_id = bot.me.id

        await bot.copy_message(
            chat_id=controller_id,
            from_chat_id=ADMIN_ID,
            message_id=source.id
        )

        await status.edit_text(
            "Post delivered to User Account.\n"
            "Sequential broadcast has been triggered."
        )

    except Exception as exc:
        await status.edit_text(
            f"Could not deliver post: {type(exc).__name__}: {exc}"
        )


@bot.on_message(filters.private & filters.command("cancel"))
@admin_only
async def cancel(_, message):
    if broadcaster.running:
        broadcaster.cancel()
        return await reply(
            message,
            "Cancellation requested. The current operation may finish first."
        )

    state = pending.pop(ADMIN_ID, None)

    if state and state.get("client"):
        try:
            await state["client"].disconnect()
        except Exception:
            pass

    await reply(
        message,
        "Current operation cancelled."
        if state else "No active operation."
    )


COMMANDS = [
    "start",
    "login",
    "string",
    "logindetails",
    "logout",
    "addbots",
    "removebots",
    "listbots",
    "sendall",
    "cancel"
]


@bot.on_message(
    filters.private
    & filters.incoming
    & ~filters.command(COMMANDS)
)
@admin_only
async def handle_input(_, message):
    state = pending.get(ADMIN_ID)

    if state:
        step = state["step"]

        try:
            if not message.text:
                return await reply(
                    message,
                    "Please send text for this step."
                )

            text = message.text.strip()

            if step == "phone":
                client, code_hash = await begin_phone_login(text)

                pending[ADMIN_ID] = {
                    "step": "otp",
                    "client": client,
                    "phone": text,
                    "hash": code_hash
                }

                await reply(
                    message,
                    "Telegram sent a login code. Send the code here."
                )
                return

            if step == "otp":
                client = state["client"]

                try:
                    me = await finish_phone_login(
                        client,
                        state["phone"],
                        state["hash"],
                        text
                    )

                except RuntimeError as exc:
                    if str(exc) == "2FA_REQUIRED":
                        pending[ADMIN_ID] = {
                            **state,
                            "step": "password",
                            "code": text
                        }

                        try:
                            await message.delete()
                        except Exception:
                            pass

                        return await reply(
                            message,
                            "Two-step verification is enabled. "
                            "Send your 2FA password."
                        )

                    raise

                pending.pop(ADMIN_ID, None)

                register_user_handler(user_session.user_client)

                try:
                    await message.delete()
                except Exception:
                    pass

                await reply(
                    message,
                    f"Login successful: {me.first_name} "
                    f"(ID: `{me.id}`)."
                )
                return

            if step == "password":
                me = await finish_phone_login(
                    state["client"],
                    state["phone"],
                    state["hash"],
                    state["code"],
                    text
                )

                pending.pop(ADMIN_ID, None)

                register_user_handler(user_session.user_client)

                try:
                    await message.delete()
                except Exception:
                    pass

                await reply(
                    message,
                    f"Login successful: {me.first_name} "
                    f"(ID: `{me.id}`)."
                )
                return

            if step == "session_string":
                me = await login_with_string(text)

                pending.pop(ADMIN_ID, None)

                register_user_handler(user_session.user_client)

                try:
                    await message.delete()
                except Exception:
                    pass

                await reply(
                    message,
                    f"Session login successful: {me.first_name} "
                    f"(ID: `{me.id}`)."
                )
                return

            if step == "add_bot":
                client = user_session.user_client

                if not client:
                    return await reply(
                        message,
                        "Connect the User Account first."
                    )

                username = text.lstrip("@")

                chat = await client.get_users(username)

                if not chat.is_bot:
                    return await reply(
                        message,
                        "That username is not a bot."
                    )

                # No internal admin-list validation is performed.
                await client.get_chat(chat.id)

                result = await add_destination(
                    chat.id,
                    chat.username or username,
                    chat.first_name or "Unnamed bot"
                )

                if result == "added":
                    pending.pop(ADMIN_ID, None)

                    total = len(await list_destinations())

                    await reply(
                        message,
                        f"Added @{chat.username or username}.\n"
                        f"Total: {total}/{MAX_BOTS}."
                    )

                elif result == "limit":
                    await reply(
                        message,
                        f"Maximum limit reached ({MAX_BOTS} bots)."
                    )

                else:
                    await reply(
                        message,
                        "That bot is already in the list."
                    )

                return

            if step == "remove_bot":
                removed = await remove_destination(text)

                pending.pop(ADMIN_ID, None)

                await reply(
                    message,
                    "Destination bot removed."
                    if removed else "That bot was not found."
                )
                return

        except RPCError as exc:
            await reply(
                message,
                f"Telegram rejected the operation: "
                f"{type(exc).__name__}."
            )
            return

        except Exception as exc:
            await reply(
                message,
                f"Error: {type(exc).__name__}: {exc}"
            )
            return

    # Save the most recently supplied post.
    if message.media or message.text:
        last_post[ADMIN_ID] = message

        await reply(
            message,
            "Post saved for broadcasting. Send /SendAll when ready."
        )


async def main():
    await init_db()

    await bot.start()

    bot.me = await bot.get_me()

    user = await start_saved_user()

    if user:
        register_user_handler(user)

    print("ABBot is running.")

    await asyncio.Event().wait()
