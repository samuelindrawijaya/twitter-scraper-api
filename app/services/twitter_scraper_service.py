import asyncio
from collections.abc import Callable
from typing import Any, Optional

from twscrape import API

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)
ProgressCallback = Callable[[str, int, int], None]


class TwitterScraperService:
    def __init__(self, safe_delay_seconds: Optional[float] = None) -> None:
        self.safe_delay_seconds = settings.SAFE_DELAY_SECONDS if safe_delay_seconds is None else safe_delay_seconds

    async def collect(
        self,
        queries: dict[str, str],
        limit_per_category: int,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> dict[str, list[Any]]:
        api = API()
        seen_ids: set[str] = set()
        results: dict[str, list[Any]] = {}
        total_rows = 0

        for category, query in queries.items():
            logger.info("Collecting category=%s query=%s", category, query)
            category_tweets: list[Any] = []

            try:
                async for tweet in api.search(query, limit=limit_per_category):
                    tweet_id = self._tweet_id(tweet)
                    if tweet_id and tweet_id in seen_ids:
                        await self._safe_delay()
                        continue
                    if tweet_id:
                        seen_ids.add(tweet_id)

                    category_tweets.append(tweet)
                    total_rows += 1

                    if progress_callback:
                        progress_callback(category, len(category_tweets), total_rows)

                    if len(category_tweets) % 100 == 0:
                        logger.info("Collected %s tweets for %s; total=%s", len(category_tweets), category, total_rows)

                    await self._safe_delay()

            except Exception as exc:
                message = str(exc).lower()
                if "no account" in message or "account" in message and "available" in message:
                    logger.error("No twscrape account available. Run twscrape add_cookie and twscrape accounts.")
                    raise RuntimeError("No twscrape account available. Configure an account with twscrape before scraping.") from exc
                if "rate" in message or "429" in message:
                    logger.warning("Rate limit while collecting category=%s: %s", category, exc)
                elif "network" in message or "timeout" in message or "connection" in message:
                    logger.warning("Network error while collecting category=%s: %s", category, exc)
                else:
                    logger.exception("Unexpected twscrape error while collecting category=%s", category)
                # Continue to preserve partial data from other categories where possible.

            if not category_tweets:
                logger.info("No results for category=%s", category)
            results[category] = category_tweets

        return results

    async def _safe_delay(self) -> None:
        if self.safe_delay_seconds > 0:
            await asyncio.sleep(self.safe_delay_seconds)

    def _tweet_id(self, tweet: Any) -> Optional[str]:
        try:
            value = getattr(tweet, "id", None) or getattr(tweet, "id_str", None)
            return str(value) if value is not None else None
        except Exception:
            logger.warning("Unexpected twscrape object shape: could not read tweet id")
            return None
