"""Kafka Consumer → Redis 캐싱 (backend 컨테이너 안에서 백그라운드로 실행)"""

import asyncio
import json
import logging

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from app.core.config import settings
from app.market.cache import save_tick
from app.strategy.engine import on_tick

log = logging.getLogger("uvicorn.error")


async def consume_forever(r) -> None:
    while True:
        consumer = AIOKafkaConsumer(
            settings.price_topic,
            bootstrap_servers=settings.kafka_bootstrap_servers,
            group_id="backend-price-cache",
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="latest",
        )
        try:
            await consumer.start()
            log.info("Kafka Consumer 시작: %s", settings.price_topic)
            async for msg in consumer:
                await save_tick(r, msg.value)
                if settings.enable_engine:
                    await on_tick(r, msg.value)  # 자동매매 전략 평가
        except KafkaConnectionError:
            log.info("Kafka 연결 대기 중...")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 어떤 오류든 로그 남기고 재시작
            log.exception("Consumer 오류, 3초 후 재시작")
            await asyncio.sleep(3)
        finally:
            await consumer.stop()
