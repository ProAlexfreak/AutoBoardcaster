from pyrogram import Client
from .config import API_ID, API_HASH
from .db import get_secret, set_secret, delete_secret

user_client = None
login_states = {}

async def start_saved_user():
    global user_client
    session = await get_secret("user_session")
    if not session:
        return None
    client = Client("abbot_user", api_id=API_ID, api_hash=API_HASH,
                    session_string=session, in_memory=True)
    await client.start()
    user_client = client
    return client

async def login_with_string(session_string: str):
    global user_client
    client = Client("abbot_user", api_id=API_ID, api_hash=API_HASH,
                    session_string=session_string.strip(), in_memory=True)
    await client.start()
    exported = await client.export_session_string()
    await set_secret("user_session", exported)
    if user_client:
        await user_client.stop()
    user_client = client
    return await client.get_me()

async def begin_phone_login(phone: str):
    client = Client("abbot_phone_login", api_id=API_ID, api_hash=API_HASH,
                    in_memory=True)
    await client.connect()
    sent = await client.send_code(phone)
    return client, sent.phone_code_hash

async def finish_phone_login(client, phone: str, phone_code_hash: str, code: str, password=None):
    global user_client
    try:
        await client.sign_in(phone, phone_code_hash, code.replace(" ", ""))
    except Exception as exc:
        # Pyrogram raises SessionPasswordNeeded when 2FA is enabled.
        if "PASSWORD" not in type(exc).__name__.upper() and "PASSWORD" not in str(exc).upper():
            raise
        if not password:
            raise RuntimeError("2FA_REQUIRED")
        await client.check_password(password)
    exported = await client.export_session_string()
    await set_secret("user_session", exported)
    me = await client.get_me()
    if user_client:
        await user_client.stop()
    user_client = client
    return me

async def logout_user():
    global user_client
    if user_client:
        await user_client.stop()
        user_client = None
    await delete_secret("user_session")
