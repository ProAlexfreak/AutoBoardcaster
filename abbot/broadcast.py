
import asyncio
import time

from pyrogram import filters
from pyrogram.errors import FloodWait, RPCError

from .config import BOT_REPLY_TIMEOUT, ADMIN_ID
from .db import list_destinations


class Broadcaster:
    def __init__(self):
        self.cancel_event = asyncio.Event()
        self.running = False
        self.on_source = None
        self.reply_waiters = {}

    def capture_reply(self, client, controller_bot_id, status_sender):

        @client.on_message(filters.private & filters.incoming)
        async def _capture(_, message):

            if not message.chat:
                return

            # Detect the post copied by ABBot into the user account's
            # private chat with ABBot.
            if (
                message.chat.id == controller_bot_id
                and message.from_user
                and message.from_user.id == controller_bot_id
                and self.on_source is not None
            ):
                self.on_source = None

                asyncio.create_task(
                    self.run(client, message, status_sender)
                )
                return

            # Capture replies from destination bots.
            chat_id = message.chat.id
            waiter = self.reply_waiters.get(chat_id)

            if (
                waiter is not None
                and message.from_user
                and message.from_user.is_bot
                and message.from_user.id == chat_id
            ):
                waiter.put_nowait(message)

    async def _wait_reply(self, queue, forwarded_id, timeout):

        deadline = time.monotonic() + timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise asyncio.TimeoutError(
                    "No matching reply received."
                )

            message = await asyncio.wait_for(
                queue.get(),
                timeout=remaining
            )

            # Only accept a reply to the exact forwarded post.
            if (
                message.reply_to_message
                and message.reply_to_message.id == forwarded_id
            ):
                return message

    async def _retry_floodwait(self, operation):

        while True:
            try:
                return await operation()

            except FloodWait as exc:
                await asyncio.sleep(exc.value)

    async def run(self, client, source_message, status_callback):

        if self.running:
            await status_callback(
                "A broadcast is already running."
            )
            return

        destinations = await list_destinations()

        if not destinations:
            await status_callback(
                "No destination bots saved. Use /AddBots first."
            )
            return

        self.running = True
        self.cancel_event.clear()

        sent = []
        failed = []

        try:
            await status_callback(
                f"Starting sequential broadcast to "
                f"{len(destinations)} bots..."
            )

            for index, (bot_id, username, first_name) in enumerate(
                destinations, 1
            ):

                if self.cancel_event.is_set():
                    break

                label = f"{first_name} (@{username})"

                # Register the queue BEFORE forwarding.
                queue = asyncio.Queue()
                self.reply_waiters[bot_id] = queue

                try:
                    forwarded = await self._retry_floodwait(
                        lambda: client.forward_messages(
                            chat_id=bot_id,
                            from_chat_id=source_message.chat.id,
                            message_ids=source_message.id
                        )
                    )

                    if isinstance(forwarded, list):
                        forwarded = forwarded[0] if forwarded else None

                    if forwarded is None:
                        raise RuntimeError(
                            "Forwarding did not return a message."
                        )

                    # Wait for the destination bot's exact reply.
                    bot_reply = await self._wait_reply(
                        queue,
                        forwarded.id,
                        BOT_REPLY_TIMEOUT
                    )

                    if self.cancel_event.is_set():
                        break

                    # Reply to the destination bot's response with
                    # the actual /broadcast command.
                    await self._retry_floodwait(
                        lambda: client.send_message(
                            chat_id=bot_id,
                            text="/broadcast",
                            reply_to_message_id=bot_reply.id
                        )
                    )

                    sent.append(label)

                    await status_callback(
                        f"Progress: {index}/{len(destinations)}\n"
                        f"Last command sent: {label}\n"
                        f"Commands sent: {len(sent)} | "
                        f"Failed: {len(failed)}"
                    )

                except asyncio.TimeoutError:
                    failed.append(
                        f"{label}: no matching reply within "
                        f"{BOT_REPLY_TIMEOUT}s"
                    )

                except RPCError as exc:
                    failed.append(
                        f"{label}: Telegram error: "
                        f"{type(exc).__name__}"
                    )

                except Exception as exc:
                    failed.append(
                        f"{label}: {type(exc).__name__}: {exc}"
                    )

                finally:
                    self.reply_waiters.pop(bot_id, None)

            cancelled = self.cancel_event.is_set()

            summary = [
                "Broadcast cancelled."
                if cancelled else "Broadcast finished.",

                f"Commands sent: {len(sent)}",
                f"Failed: {len(failed)}",

                "",
                "Note: Command sent does not confirm "
                "that the destination bot published the post."
            ]

            if failed:
                summary.append("\nFailures:")
                summary.extend(
                    f"• {item}" for item in failed[:30]
                )

            await status_callback("\n".join(summary))

        finally:
            self.reply_waiters.clear()
            self.running = False

    def cancel(self):
        self.cancel_event.set()


broadcaster = Broadcaster()
