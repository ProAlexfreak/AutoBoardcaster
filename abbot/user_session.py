
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

from .config import API_ID, API_HASH
from .db import get_secret, set_secret, delete_secret


user_client = None


def _new_client(name, session_string=None):
    return Client(
        name,
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=session_string,
        in_memory=True
    )


async def _replace_user_client(client):
    """Replace the active user client safely."""
    global user_client

    old_client = user_client

    user_client = client

    if old_client and old_client is not client:
        try:
            await old_client.stop()
        except Exception:
            pass


async def start_saved_user():
    """Restore the previously saved user session."""
    global user_client

    if user_client and user_client.is_connected:
        return user_client

    session = await get_secret("user_session")

    if not session:
        return None

    client = _new_client("abbot_user", session)

    try:
        await client.start()
        user_client = client
        return client

    except Exception:
        if client.is_connected:
            try:
                await client.stop()
            except Exception:
                pass
        raise


async def login_with_string(session_string: str):
    """Login using a Pyrogram session string."""
    if not session_string or not session_string.strip():
        raise ValueError("Session string cannot be empty.")

    client = _new_client(
        "abbot_user",
        session_string.strip()
    )

    try:
        await client.start()

        # Verify that the session is authorized.
        me = await client.get_me()

        exported = await client.export_session_string()

        await set_secret("user_session", exported)

        await _replace_user_client(client)

        return me

    except Exception:
        if client.is_connected:
            try:
                await client.stop()
            except Exception:
                pass
        raise


async def begin_phone_login(phone: str):
    """Begin phone-number authentication."""
    if not phone or not phone.strip():
        raise ValueError("Phone number cannot be empty.")

    client = _new_client("abbot_phone_login")

    try:
        await client.connect()

        sent = await client.send_code(phone.strip())

        return client, sent.phone_code_hash

    except Exception:
        if client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass
        raise


async def finish_phone_login(
    client,
    phone: str,
    phone_code_hash: str,
    code: str,
    password=None
):
    """Finish phone login, including optional Telegram 2FA."""
    if not code or not code.strip():
        raise ValueError("Login code cannot be empty.")

    try:
        await client.sign_in(
            phone,
            phone_code_hash,
            code.replace(" ", "").strip()
        )

    except SessionPasswordNeeded:
        if not password:
            raise RuntimeError("2FA_REQUIRED")

        await client.check_password(password)

    try:
        me = await client.get_me()

        exported = await client.export_session_string()

        await set_secret("user_session", exported)

        await _replace_user_client(client)

        return me

    except Exception:
        if client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass
        raise


async def logout_user():
    """Disconnect and remove the saved session."""
    global user_client

    client = user_client
    user_client = None

    if client:
        try:
            if client.is_connected:
                await client.stop()
        except Exception:
            pass

    await delete_secret("user_session")
