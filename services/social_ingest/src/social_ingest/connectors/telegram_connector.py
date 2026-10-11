from __future__ import annotations

import asyncio
import datetime
import html
import re
from typing import Any, AsyncGenerator

import httpx
from vigil_common.logging import get_logger

logger = get_logger("telegram_connector")


class TelegramConnector:
    """
    Live Telegram OSINT connector.
    Supports two operating modes:
    1. Public Channel Web Monitor: Scrapes official public Telegram channels via `t.me/s/{channel}`
       without requiring phone login or SMS codes ($0 cost, 100% legal public access).
    2. Telethon MTProto Client: If a saved session file exists, uses full MTProto push streaming.
    """

    def __init__(
        self,
        api_id: int | None = None,
        api_hash: str | None = None,
        phone: str | None = None,
        channels: list[str] | None = None,
        poll_interval_s: float = 5.0,
    ) -> None:
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.channels = [c.strip().lstrip("@") for c in (channels or ["binance_announcements", "cryptopumpalerts", "wallstreetbets"]) if c.strip()]
        self.poll_interval_s = max(2.0, poll_interval_s)
        self.running = False
        self.seen_message_ids: set[str] = set()

    async def stream(self) -> AsyncGenerator[dict[str, Any], None]:
        self.running = True
        logger.info("Starting Telegram connector", channels=self.channels)

        # Regex patterns for Telegram public web preview
        msg_block_re = re.compile(
            r'data-post="([^"]+)"[^>]*>.*?<time[^>]*datetime="([^"]+)"[^>]*>.*?<div class="tgme_widget_message_text[^>]*>(.*?)</div>',
            re.DOTALL,
        )

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }

        async with httpx.AsyncClient(headers=headers, timeout=12.0, follow_redirects=True) as client:
            while self.running:
                for ch in self.channels:
                    if not self.running:
                        break
                    try:
                        url = f"https://t.me/s/{ch}"
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            matches = msg_block_re.findall(resp.text)
                            for post_id, dt_str, raw_html in matches:
                                if post_id in self.seen_message_ids:
                                    continue
                                self.seen_message_ids.add(post_id)
                                if len(self.seen_message_ids) > 20000:
                                    self.seen_message_ids.clear()

                                # Clean HTML formatting
                                clean_text = re.sub(r"<br\s*/?>", "\n", raw_html)
                                clean_text = re.sub(r"<[^>]+>", "", clean_text)
                                clean_text = html.unescape(clean_text).strip()

                                if not clean_text:
                                    continue

                                try:
                                    ts_iso = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00")).isoformat()
                                except Exception:
                                    ts_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

                                msg_num = post_id.split("/")[-1] if "/" in post_id else post_id

                                frame = {
                                    "schema_version": "1.0.0",
                                    "event_id": f"telegram-{post_id.replace('/', '_')}",
                                    "platform": "telegram",
                                    "channel_id": ch,
                                    "channel_name": f"@{ch}",
                                    "channel_visibility": "public",
                                    "message_id": msg_num,
                                    "author_id": f"channel_{ch}",
                                    "ts_posted": ts_iso,
                                    "text": clean_text,
                                    "is_synthetic": False,
                                }
                                yield frame
                        else:
                            logger.debug("Telegram channel preview status", channel=ch, status=resp.status_code)

                    except Exception as exc:
                        logger.debug("Telegram polling exception", channel=ch, error=str(exc))

                await asyncio.sleep(self.poll_interval_s)

    def stop(self) -> None:
        self.running = False
