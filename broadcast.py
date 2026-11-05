import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait, RPCError
from .config import BOT_REPLY_TIMEOUT, POST_COMMAND_DELAY
from .db import list_destinations

class Broadcaster:
    def __init__(self):
        self.cancel_event = asyncio.Event()
        self.running = False
        self.last_source = None
        self.reply_waiters = {}

    def capture_reply(self, client, controller_bot_id, status_sender):
        @client.on_message(filters.private & filters.incoming)
        async def _capture(_, message):
            # ABBot copies the selected post into the user account's Saved/DM chat.
            if (message.chat and message.chat.id == (await client.get_me()).id
                    and message.from_user and message.from_user.id == controller_bot_id
                    and self.on_source is not None):
                source_callback = self.on_source
                self.on_source = None
                asyncio.create_task(self.run(client, message, status_sender))
                return

            chat_id = message.chat.id
            waiter = self.reply_waiters.get(chat_id)
            if waiter and not waiter.done():
                waiter.set_result(message)

    on_source = None

    async def _wait_reply(self, chat_id, timeout):
        future = asyncio.get_running_loop().create_future()
        self.reply_waiters[chat_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.reply_waiters.pop(chat_id, None)

    async def run(self, client, source_message, status_callback):
        if self.running:
            await status_callback("A broadcast is already running.")
            return
        destinations = await list_destinations()
        if not destinations:
            await status_callback("No destination bots saved. Use /AddBots first.")
            return
        self.running = True
        self.cancel_event.clear()
        success, failed = [], []
        try:
            await status_callback(f"Starting sequential broadcast to {len(destinations)} bots…")
            for index, (bot_id, username, first_name) in enumerate(destinations, 1):
                if self.cancel_event.is_set():
                    break
                label = f"{first_name} (@{username})"
                try:
                    # Forward the admin's original post to the destination bot.
                    forwarded = await client.forward_messages(
                        chat_id=bot_id,
                        from_chat_id=source_message.chat.id,
                        message_ids=source_message.id
                    )
                    if isinstance(forwarded, list):
                        forwarded = forwarded[0]

                    # Wait for the destination bot's reply to that forwarded post.
                    reply = await self._wait_reply(bot_id, BOT_REPLY_TIMEOUT)
                    if reply.reply_to_message and reply.reply_to_message.id != forwarded.id:
                        raise TimeoutError("Received a reply, but it did not reference the forwarded post.")

                    # Send /broadcast as a reply to the bot's response.
                    await client.send_message(
                        chat_id=bot_id,
                        text="/broadcast",
                        reply_to_message_id=reply.id
                    )
                    await asyncio.sleep(POST_COMMAND_DELAY)
                    success.append(label)
                    await status_callback(
                        f"Progress: {index}/{len(destinations)}\n"
                        f"Last completed: {label}\n"
                        f"Successful: {len(success)} | Failed: {len(failed)}"
                    )
                except FloodWait as exc:
                    failed.append(f"{label}: FloodWait {exc.value}s")
                    await status_callback(f"Rate limit from {label}; skipped. Wait: {exc.value}s")
                except (TimeoutError, asyncio.TimeoutError):
                    failed.append(f"{label}: no matching bot reply within {BOT_REPLY_TIMEOUT}s")
                except RPCError as exc:
                    failed.append(f"{label}: Telegram error: {type(exc).__name__}")
                except Exception as exc:
                    failed.append(f"{label}: {type(exc).__name__}: {exc}")
            cancelled = self.cancel_event.is_set()
            summary = [
                "Broadcast cancelled." if cancelled else "Broadcast finished.",
                f"Successful: {len(success)}",
                f"Failed: {len(failed)}",
            ]
            if failed:
                summary.append("\nFailures:\n" + "\n".join(f"• {x}" for x in failed[:30]))
            await status_callback("\n".join(summary))
        finally:
            self.running = False

    def cancel(self):
        self.cancel_event.set()

broadcaster = Broadcaster()
