"""시세 수집기 (collector 컨테이너)

시세 소스에서 데이터를 받아 Kafka 토픽(stock.price)으로 보낸다.
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
    source = create_source(settings.market_source)
    producer = await start_producer()
    try:
        while True:
            for tick in source.next_ticks():
                await producer.send(settings.price_topic, tick, key=tick["symbol"])
            await asyncio.sleep(settings.tick_interval_sec)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
