
import aiosqlite
from cryptography.fernet import Fernet, InvalidToken

from .config import DB_PATH, ENCRYPTION_KEY


_cipher = Fernet(ENCRYPTION_KEY)


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS destinations (
                bot_id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL
            )
        """)

        await db.commit()


async def set_secret(key: str, value: str):
    """Encrypt and securely store a secret."""

    if not isinstance(value, str) or not value:
        raise ValueError("Secret value cannot be empty.")

    encrypted = _cipher.encrypt(value.encode("utf-8"))

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
            """,
            (key, encrypted)
        )

        await db.commit()


async def get_secret(key: str):
    """Retrieve and decrypt a stored secret."""

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,)
        ) as cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    try:
        return _cipher.decrypt(row[0]).decode("utf-8")

    except InvalidToken as exc:
        raise RuntimeError(
            "Could not decrypt saved session. "
            "Check that ENCRYPTION_KEY has not changed."
        ) from exc


async def delete_secret(key: str):
    """Delete a stored secret."""

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM settings WHERE key = ?",
            (key,)
        )

        await db.commit()


async def list_destinations():
    """Return all saved destination bots."""

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT bot_id, username, first_name
            FROM destinations
            ORDER BY first_name COLLATE NOCASE
        """) as cursor:
            return await cursor.fetchall()


async def add_destination(
    bot_id: int,
    username: str,
    first_name: str
):
    """Add a destination bot, with a maximum of 30."""

    username = username.strip().lstrip("@").lower()
    first_name = first_name.strip() or "Unnamed bot"

    if not bot_id or not username:
        raise ValueError("Bot ID and username are required.")

    async with aiosqlite.connect(DB_PATH) as db:

        # Prevent simultaneous additions from exceeding the limit.
        await db.execute("BEGIN IMMEDIATE")

        try:
            async with db.execute(
                """
                SELECT 1 FROM destinations
                WHERE bot_id = ? OR username = ?
                """,
                (bot_id, username)
            ) as cursor:
                if await cursor.fetchone():
                    await db.rollback()
                    return "duplicate"

            async with db.execute(
                "SELECT COUNT(*) FROM destinations"
            ) as cursor:
                count = (await cursor.fetchone())[0]

            if count >= 30:
                await db.rollback()
                return "limit"

            await db.execute(
                """
                INSERT INTO destinations
                (bot_id, username, first_name)
                VALUES (?, ?, ?)
                """,
                (bot_id, username, first_name)
            )

            await db.commit()
            return "added"

        except Exception:
            await db.rollback()
            raise


async def remove_destination(username: str):
    """Remove a destination bot by username."""

    username = username.strip().lstrip("@").lower()

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            DELETE FROM destinations
            WHERE lower(username) = ?
            """,
            (username,)
        )

        await db.commit()

        return cursor.rowcount > 0
