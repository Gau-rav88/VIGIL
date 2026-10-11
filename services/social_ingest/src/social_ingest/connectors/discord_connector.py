from __future__ import annotations

import asyncio
import datetime
from typing import Any, AsyncGenerator

import discord
from vigil_common.logging import get_logger

logger = get_logger("discord_connector")


class DiscordConnector:
    """
    Live Discord OSINT connector.
    Connects to Discord Gateway WebSocket with the bot token.
    Monitors messages from configured channel IDs (or all visible channels if empty).
    Streams normalized raw frames to social_ingest.
    """

    def __init__(self, bot_token: str, channel_ids: list[str] | None = None) -> None:
        self.bot_token = bot_token.strip()
        self.channel_ids = {c.strip() for c in (channel_ids or []) if c.strip()}
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=10000)
        self.running = False
        self.client: discord.Client | None = None
        self.bot_task: asyncio.Task[None] | None = None

    async def start(self) -> AsyncGenerator[dict[str, Any], None]:
        self.running = True
        intents = discord.Intents.default()
        intents.message_content = True

        connector_self = self

        class VigilDiscordClient(discord.Client):
            async def on_ready(self) -> None:
                logger.info(
                    "Discord OSINT Bot connected",
                    bot_user=str(self.user),
                    bot_id=self.user.id if self.user else None,
                    monitoring_channels=list(connector_self.channel_ids) or "ALL",
                )

            async def on_message(self, message: discord.Message) -> None:
                if not connector_self.running:
                    return
                # Ignore self messages
                if self.user and message.author.id == self.user.id:
                    return

                ch_id = str(message.channel.id)
                # Filter if target channels specified
                if connector_self.channel_ids and ch_id not in connector_self.channel_ids:
                    return

                content = message.content or ""
                if not content.strip():
                    return

                channel_name = getattr(message.channel, "name", "discord-channel")
                ts_iso = message.created_at.replace(tzinfo=datetime.timezone.utc).isoformat()

                frame = {
                    "schema_version": "1.0.0",
                    "event_id": f"discord-{message.id}",
                    "platform": "discord",
                    "channel_id": ch_id,
                    "channel_name": channel_name,
                    "channel_visibility": "public",
                    "message_id": str(message.id),
                    "author_id": str(message.author.id),
                    "ts_posted": ts_iso,
                    "text": content,
                    "is_synthetic": False,
                }

                try:
                    connector_self.queue.put_nowait(frame)
                except asyncio.QueueFull:
                    logger.warning("Discord queue full, dropping message", msg_id=message.id)

        self.client = VigilDiscordClient(intents=intents)

        async def _run_bot() -> None:
            try:
                assert self.client is not None
                await self.client.start(self.bot_token)
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                logger.error("Discord bot runner error", error=str(exc))

        self.bot_task = asyncio.create_task(_run_bot())

        while self.running:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                yield item
            except asyncio.TimeoutError:
                continue

    async def stop(self) -> None:
        self.running = False
        if self.client and not self.client.is_closed():
            await self.client.close()
        if self.bot_task and not self.bot_task.done():
            self.bot_task.cancel()
            try:
                await self.bot_task
            except asyncio.CancelledError:
                pass
        logger.info("Discord connector stopped cleanly")
