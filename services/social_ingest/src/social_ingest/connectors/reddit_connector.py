from __future__ import annotations

import asyncio
import datetime
from typing import Any, AsyncGenerator

import httpx
from vigil_common.logging import get_logger

logger = get_logger("reddit_connector")


class RedditConnector:
    """
    Reddit live OSINT connector.
    Connects to Reddit OAuth2 API to stream new submissions & comments
    from target subreddits (e.g. wallstreetbets, CryptoCurrency, pennystocks).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str = "vigil:v1.0 (forensic surveillance platform)",
        subreddits: list[str] | None = None,
        poll_interval_s: float = 5.0,
    ) -> None:
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.user_agent = user_agent.strip()
        self.subreddits = [s.strip().lstrip("r/") for s in (subreddits or ["wallstreetbets", "CryptoCurrency", "pennystocks"]) if s.strip()]
        self.poll_interval_s = max(2.0, poll_interval_s)
        self.running = False
        self.seen_ids: set[str] = set()
        self.access_token: str | None = None
        self.token_expiry: float = 0.0

    async def _refresh_token(self, client: httpx.AsyncClient) -> bool:
        if not self.client_id or not self.client_secret or self.client_id == "your_client_id_here":
            return False
        try:
            auth = (self.client_id, self.client_secret)
            resp = await client.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": self.user_agent},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                expires_in = data.get("expires_in", 3600)
                self.token_expiry = datetime.datetime.now(datetime.timezone.utc).timestamp() + expires_in - 60
                logger.info("Obtained Reddit OAuth2 access token")
                return True
            else:
                logger.warning("Reddit OAuth2 auth failed", status=resp.status_code, body=resp.text[:200])
                return False
        except Exception as exc:
            logger.warning("Error fetching Reddit token", error=str(exc))
            return False

    async def stream(self) -> AsyncGenerator[dict[str, Any], None]:
        self.running = True
        logger.info("Starting Reddit connector", subreddits=self.subreddits)

        async with httpx.AsyncClient(timeout=15.0) as client:
            while self.running:
                now_ts = datetime.datetime.now(datetime.timezone.utc).timestamp()
                if not self.access_token or now_ts >= self.token_expiry:
                    success = await self._refresh_token(client)
                    if not success:
                        # Wait before retry if unauthenticated
                        await asyncio.sleep(30.0)
                        continue

                for sub in self.subreddits:
                    if not self.running:
                        break
                    try:
                        headers = {
                            "Authorization": f"Bearer {self.access_token}",
                            "User-Agent": self.user_agent,
                        }
                        url = f"https://oauth.reddit.com/r/{sub}/new?limit=25"
                        resp = await client.get(url, headers=headers)
                        if resp.status_code == 200:
                            listing = resp.json().get("data", {}).get("children", [])
                            for child in listing:
                                post = child.get("data", {})
                                post_id = post.get("name") or post.get("id")
                                if not post_id or post_id in self.seen_ids:
                                    continue
                                self.seen_ids.add(post_id)
                                if len(self.seen_ids) > 20000:
                                    self.seen_ids.clear()

                                title = post.get("title", "")
                                selftext = post.get("selftext", "")
                                text = f"{title}\n\n{selftext}".strip() if selftext else title
                                if not text:
                                    continue

                                author = post.get("author", "unknown_redditor")
                                created_utc = post.get("created_utc", now_ts)
                                ts_iso = datetime.datetime.fromtimestamp(created_utc, datetime.timezone.utc).isoformat()

                                frame = {
                                    "schema_version": "1.0.0",
                                    "event_id": f"reddit-{post_id}",
                                    "platform": "reddit",
                                    "channel_id": f"r/{sub}",
                                    "channel_name": f"r/{sub}",
                                    "channel_visibility": "public",
                                    "message_id": str(post_id),
                                    "author_id": str(author),
                                    "ts_posted": ts_iso,
                                    "text": text,
                                    "is_synthetic": False,
                                }
                                yield frame
                        elif resp.status_code == 401:
                            self.access_token = None
                    except Exception as exc:
                        logger.debug("Error polling Reddit subreddit", subreddit=sub, error=str(exc))

                await asyncio.sleep(self.poll_interval_s)

    def stop(self) -> None:
        self.running = False
