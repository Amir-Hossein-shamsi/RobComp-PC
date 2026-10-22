import asyncio
import json
import logging
import os
import random
import signal
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
import websockets
from websockets.exceptions import WebSocketException
from common.config import settings


# Config
DEFAULT_WS_URL = os.getenv("LIGHTSTREAMER_URL", "wss://push2v7.*.*/lightstreamer")
USE_MOCK = os.getenv("USE_MOCK", "").lower() == "true"

SYMBOLS = os.getenv("SYMBOLS", "AAPL,MSFT,NVDA,TSLA,AMZN,GOOGL,META,AMD,SPY,QQQ").split(",")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger("worker_a")



def build_subscribe_message(items: list[str]) -> str:
    fields = ["LastPrice", "Bid", "Ask", "Volume", "Timestamp"]
    items_str = ",".join(items)
    return f"subscribe,MERGE,{items_str},Quote,{','.join(fields)}"


def parse_lightstreamer_message(raw: str) -> Optional[Dict[str, Any]]:
    if not raw.startswith("data|"):
        return None
    parts = raw.split("|")
    if len(parts) < 3:
        return None
    symbol = parts[1]
    record = {"symbol": symbol}
    for field in parts[2:]:
        if "=" not in field:
            continue
        k, v = field.split("=", 1)
        if k in ("LastPrice", "Bid", "Ask", "Volume"):
            try:
                record[k] = float(v)
            except ValueError:
                record[k] = v
        elif k == "Timestamp":
            try:
                record[k] = int(v)
            except ValueError:
                record[k] = v
        else:
            record[k] = v
    return record


class MockLightstreamer:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.prices = {sym: 100.0 + random.random() * 200 for sym in symbols}

    def next_message(self) -> str:
        symbol = random.choice(self.symbols)
        self.prices[symbol] += random.uniform(-1.0, 1.0)
        price = round(self.prices[symbol], 2)
        bid = round(price - random.uniform(0.01, 0.10), 2)
        ask = round(price + random.uniform(0.01, 0.10), 2)
        volume = int(random.uniform(100, 10000))
        ts = int(datetime.now(timezone.utc).timestamp())
        return (
            f"data|{symbol}|LastPrice={price}|Bid={bid}|Ask={ask}|"
            f"Volume={volume}|Timestamp={ts}"
        )



class WorkerA:
    def __init__(self):
        self._stop = asyncio.Event()
        self._redis: Optional[aioredis.Redis] = None
        self._ws_url = os.getenv("LIGHTSTREAMER_URL", DEFAULT_WS_URL)
        self._mock = MockLightstreamer(SYMBOLS)   
        self._symbols = SYMBOLS

    async def _publish_record(self, record: Dict[str, Any]) -> None:
        if not self._redis:
            return
        payload = {
            "symbol": record.get("symbol"),
            "price": record.get("LastPrice") or record.get("price"),
            "bid": record.get("Bid") or record.get("bid"),
            "ask": record.get("Ask") or record.get("ask"),
            "day_volume": record.get("Volume") or record.get("day_volume"),
            "currency": record.get("Currency", "USD"),
            "exchange": record.get("Exchange", "UNKNOWN"),
            "timestamp": record.get("Timestamp") or int(datetime.now(timezone.utc).timestamp()),
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        await self._redis.publish(settings.REDIS_CHANNEL, json.dumps(payload))

    async def _consume_real(self) -> None:
        async with websockets.connect(
            self._ws_url,
            ping_interval=20,
            ping_timeout=20,
        ) as websocket:
            logger.info("Connected to Lightstreamer at %s", self._ws_url)
            subscribe_msg = build_subscribe_message(self._symbols)
            await websocket.send(subscribe_msg)
            logger.info("Subscribed to symbols: %s", ", ".join(self._symbols))
            async for raw in websocket:
                if self._stop.is_set():
                    break
                if not raw:
                    continue
                record = parse_lightstreamer_message(raw)
                if record is None:
                    logger.debug("Unrecognised message format: %s", raw[:100])
                    continue
                await self._publish_record(record)
                logger.info("Published: %s @ %.2f", record.get("symbol"), record.get("LastPrice"))

    async def _consume_mock(self) -> None:
        logger.info("Starting mock data generator for symbols: %s", ", ".join(self._symbols))
        while not self._stop.is_set():
            raw = self._mock.next_message()
            record = parse_lightstreamer_message(raw)
            if record is None:
                continue
            await self._publish_record(record)
            logger.info("[MOCKing : ] Published: %s @ %.2f", record.get("symbol"), record.get("LastPrice"))
            await asyncio.sleep(random.uniform(0.3, 0.7))

    async def run(self) -> None:
        masked_url = settings.redis_url.replace(settings.REDIS_PASSWORD, "****") if settings.REDIS_PASSWORD else settings.redis_url
        logger.info("Connecting to Redis with URL: %s", masked_url)

        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        await self._redis.ping()
        logger.info("Connected to Redis at %s", settings.REDIS_HOST)

        try:
            if USE_MOCK:
                logger.warning("Running in MOCK mode (environment variable USE_MOCK=true).")
                await self._consume_mock()
            else:
                delay = 1.0
                while not self._stop.is_set():
                    try:
                        await self._consume_real()
                        break
                    except (WebSocketException, ConnectionRefusedError, OSError) as exc:
                        logger.error("Real feed connection error: %s. Retrying in %.1fs", exc, delay)
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 30)
                        if delay > 20:
                            logger.warning("Too many real feed failures – switching to MOCK mode.")
                            await self._consume_mock()
                            break
        finally:
            if self._redis:
                await self._redis.aclose()

    def stop(self):
        self._stop.set()


async def main():
    worker = WorkerA()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:
            pass
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())