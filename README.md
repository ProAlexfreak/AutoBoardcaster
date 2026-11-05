# ABBot Multi-Bot Broadcaster

A Telegram bot controller + one Pyrogram user account ("userbot") that sequentially interacts with up to **30** destination bots.

## Workflow

1. An authorized admin forwards a post (or sends a message/media) to ABBot.
2. Admin sends `/SendAll`.
3. ABBot copies the post to the configured user account.
4. The logged-in user account forwards it to each saved destination bot, one at a time.
5. It waits for that bot's reply to the forwarded post, then replies to that reply with `/broadcast`.
6. It proceeds to the next destination bot and reports the result.

**Important:** This project automates interactions with third-party Telegram bots using a user account. Use it only with bots you control or are authorized to operate, respect Telegram rate limits and each bot's rules, and do not use it for unsolicited messaging. Bot replies differ; the response-matching and completion rules may need adapting to your destination bots.

## Features

- `/login` phone + OTP + optional 2FA flow
- `/string` Pyrogram session-string login
- `/LoginDetails`, `/Logout`
- `/AddBots`, `/RemoveBots`, `/ListBots` (30 maximum)
- `/SendAll`, `/Cancel`, `/Start`
- SQLite storage; session string encrypted at rest with Fernet
- Admin-only controls; no session string or password shown in `/LoginDetails`

## Requirements

- Python 3.10+
- Telegram API ID and API hash from https://my.telegram.org
- A Telegram bot token from BotFather
- Your numeric Telegram user ID as `ADMIN_ID`
- The user account must have started ABBot and must already have started each destination bot and have the required admin permissions there.

## Setup

```bash
git clone <your-repo-url>
cd abbot-broadcaster
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env`:

```env
BOT_TOKEN=123456:your_bot_token
API_ID=123456
API_HASH=your_api_hash
ADMIN_ID=123456789
ENCRYPTION_KEY=generate-a-fernet-key
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Run:

```bash
python -m abbot
```

## Commands

| Command | Description |
|---|---|
| `/start` | Overview and status |
| `/login` | Login by phone number, OTP, and optional 2FA |
| `/string` | Login using a Pyrogram session string |
| `/logindetails` | Show connected account details |
| `/logout` | Disconnect and clear stored session |
| `/addbots` | Add a destination bot by username |
| `/removebots` | Remove a destination bot by username |
| `/listbots` | List saved destination bots |
| `/sendall` | Broadcast the most recently received post |
| `/cancel` | Cancel the active broadcast |

## Login security

- Keep `.env`, the SQLite database and backups private.
- Never share OTPs, 2FA passwords, session strings, or the encryption key.
- Use a private deployment and restrict server access.
- If a session is exposed, terminate it from Telegram's **Settings → Devices**.
- The session is encrypted in SQLite, but anyone with both the database and encryption key can decrypt it.

## Deployment

Use a persistent disk/volume because `abbot.db` stores the encrypted session and destination list. Set all environment variables in your host's secret manager. Run one worker/instance only; multiple instances can cause duplicate broadcasts and session conflicts.

## Notes / limitations

- This is a functional starter implementation, not a guarantee that every third-party bot uses the same reply protocol.
- Destination validation checks that the username resolves and that the user account can open the bot chat. Telegram does not expose a universal API to verify arbitrary custom "admin lists"; the destination bot's own behavior is authoritative.
- The broadcaster waits for a reply to the forwarded message, sends `/broadcast` as a reply to that bot response, then waits briefly before continuing. Tune `BOT_REPLY_TIMEOUT` and `POST_COMMAND_DELAY` for your bots.
- A bot may reject commands, require extra steps, or rate-limit the account. Failed destinations are reported and skipped.
