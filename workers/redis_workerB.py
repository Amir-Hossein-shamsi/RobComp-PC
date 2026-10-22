from __future__ import annotations

import asyncio
import json
import logging
import signal
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from common.config import settings
from common.db import SessionFactory, init_schema
from common.models import RTDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("worker_b")


class MarketDataWorker:
    def __init__(self) -> None:
        self._buffer: list[dict[str, Any]] = []
        self._buffer_lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._redis: aioredis.Redis | None = None

    @staticmethod
    def _to_datetime(ts: Any) -> datetime | None:
        if ts is None:
            return None
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc)
        except (ValueError, OSError, TypeError):
            return None

    def _normalize_record(self, raw: bytes | str) -> dict[str, Any] | None:
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Dropping malformed JSON message: %s", exc)
            return None

        symbol = payload.get("symbol")
        if not symbol:
            logger.debug("Dropping message without symbol: %s", payload)
            return None

        return {
            "symbol": str(symbol)[:32],
            "exchange": payload.get("exchange"),
            "currency": payload.get("currency"),
            "event_type": payload.get("event") or payload.get("type"),
            "price": payload.get("price"),
            "bid": payload.get("bid"),
            "ask": payload.get("ask"),
            "day_volume": payload.get("day_volume"),
            "source_ts": self._to_datetime(payload.get("timestamp")),
        }

    
    async def _flush(self) -> None:
        
        async with self._buffer_lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []

        try:
            async with SessionFactory() as session:
                async with session.begin():
                    session.add_all([RTDS(**row) for row in batch])
            logger.info("Persisted %d rows to RTDS.", len(batch))
        except SQLAlchemyError as exc:
            logger.error("DB write failed for %d rows: %s", len(batch), exc)
            async with self._buffer_lock:
                self._buffer = batch + self._buffer

    async def _periodic_flush(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=settings.FLUSH_INTERVAL)
            except asyncio.TimeoutError:
                pass
            await self._flush()

    async def _consume(self) -> None:
        assert self._redis is not None
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(settings.REDIS_CHANNEL)
        logger.info("Subscribed to Redis channel '%s'.", settings.REDIS_CHANNEL)

        try:
            async for message in pubsub.listen():
                if self._stop.is_set():
                    break
                if message.get("type") != "message":
                    continue

                record = self._normalize_record(message["data"])
                if record is None:
                    continue

                async with self._buffer_lock:
                    self._buffer.append(record)
                    should_flush = len(self._buffer) >= settings.BATCH_SIZE
                if should_flush:
                    await self._flush()
        finally:
            await pubsub.unsubscribe(settings.REDIS_CHANNEL)
            await pubsub.aclose()

    async def run(self) -> None:
        await init_schema()
        flusher = asyncio.create_task(self._periodic_flush(), name="periodic-flush")

        delay = 1.0
        try:
            while not self._stop.is_set():
                try:
                    self._redis = aioredis.from_url(
                        settings.redis_url, decode_responses=False
                    )
                    await self._redis.ping()
                    logger.info("Connected to Redis at %s.", settings.REDIS_HOST)
                    delay = 1.0  
                    await self._consume()
                except (RedisError, OSError) as exc:
                    if self._stop.is_set():
                        break
                    logger.error(
                        "Redis connection lost (%s). Reconnecting in %.1fs.", exc, delay
                    )
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, settings.RECONNECT_MAX_DELAY)
                finally:
                    if self._redis is not None:
                        await self._redis.aclose()
                        self._redis = None
        finally:
            self._stop.set()
            flusher.cancel()
            await self._flush() 
            logger.info("Worker B stopped cleanly.")

    def request_stop(self) -> None:
        logger.info("Shutdown signal received.")
        self._stop.set()


async def main() -> None:
    worker = MarketDataWorker()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.request_stop)
        except NotImplementedError:
            pass  
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
