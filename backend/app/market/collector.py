"""시세 수집기 (collector 컨테이너)

시세 소스에서 데이터를 받아 Kafka 토픽(stock.price)으로 보낸다.
- mock: 가상 시세 1초마다 (기본 종목 + 켜진 전략 종목)
- kiwoom: 팀 키로 실시간 WebSocket 구독 (구독 종목은 Redis를 보고 동적으로 맞춤)
실행: python -m app.market.collector
"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.market.sources import create_source

logging.basicConfig(level=logging.INFO, format="%(asctime)s [collector] %(message)s")
log = logging.getLogger(__name__)
SYNC_EVERY = 3  # 모의 시세: 몇 번 생성할 때마다 전략 종목을 다시 볼지


async def start_producer() -> AIOKafkaProducer:
    """Kafka가 뜰 때까지 재시도하며 Producer를 연결한다."""
    while True:
        producer = AIOKafkaProducer(
            bootstrap_servers=settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
            key_serializer=lambda k: k.encode(),
        )
        try:
            await producer.start()
            log.info("Kafka 연결 성공: %s", settings.kafka_bootstrap_servers)
            return producer
        except KafkaConnectionError:
            await producer.stop()
            log.info("Kafka 연결 대기 중...")
            await asyncio.sleep(3)


async def run() -> None:
    import redis.asyncio as aioredis

    from app.kiwoom import platform

    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    source = create_source(settings.market_source, redis=r)
    producer = await start_producer()
    try:
        if hasattr(source, "stream"):  # 키움: 실시간 WebSocket
            async for ticks in source.stream():
                for tick in ticks:
                    await producer.send(settings.price_topic, tick, key=tick["symbol"])
        else:  # 모의 시세: 1초마다 생성, 켜진 전략 종목은 SYNC_EVERY초마다 맞춤
            n = 0
            while True:
                if n % SYNC_EVERY == 0:
                    try:
                        await source.sync()
                    except Exception:  # noqa: BLE001
                        log.exception("전략 종목 맞추기 실패")
                n += 1
                for tick in source.next_ticks():
                    await producer.send(settings.price_topic, tick, key=tick["symbol"])
                await asyncio.sleep(settings.tick_interval_sec)
    finally:
        await producer.stop()
        await platform.close_team_client()
        await r.aclose()


if __name__ == "__main__":
    asyncio.run(run())
