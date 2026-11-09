"""Kafka 실시간 이상탐지 루프

stock.price 토픽의 시세를 받아 StreamDetector로 검사하고,
이상 징후가 있으면 다음 세 곳에 남긴다.
- Kafka  stock.anomaly 토픽     (다른 서비스가 구독 가능)
- Redis  anomalies 리스트       (backend /anomalies API가 조회)
- Redis  alerts 리스트 + 채널   (자동매매 주문과 같은 통합 알림 피드)
"""

import asyncio
import json
import logging
import os

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

from anomaly.detector import StreamDetector

log = logging.getLogger("uvicorn.error")

KAFKA = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PRICE_TOPIC = os.getenv("PRICE_TOPIC", "stock.price")
ANOMALY_TOPIC = os.getenv("ANOMALY_TOPIC", "stock.anomaly")
ANOMALIES_KEY, ALERTS_KEY = "anomalies", "alerts"
MAX_KEEP = 200


async def save_alert(r, alert: dict) -> None:
    data = json.dumps(alert, ensure_ascii=False)
    pipe = r.pipeline()
    pipe.lpush(ANOMALIES_KEY, data)
    pipe.ltrim(ANOMALIES_KEY, 0, MAX_KEEP - 1)
    pipe.lpush(ALERTS_KEY, data)
    pipe.ltrim(ALERTS_KEY, 0, 99)
    pipe.publish(ALERTS_KEY, data)
    await pipe.execute()


async def handle(detector: StreamDetector, tick: dict, r, producer=None) -> dict | None:
    alert = detector.process(tick)
    if alert:
        await save_alert(r, alert)
        if producer:
            await producer.send(ANOMALY_TOPIC, alert, key=alert["symbol"])
        log.info("%s (%s)", alert["message"], alert["level"])
    return alert


async def run(detector: StreamDetector, r) -> None:
    while True:
        consumer = AIOKafkaConsumer(PRICE_TOPIC, bootstrap_servers=KAFKA, group_id="ai-anomaly",
                                    value_deserializer=lambda v: json.loads(v.decode()), auto_offset_reset="latest")
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA, key_serializer=lambda k: k.encode(),
                                    value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode())
        try:
            await consumer.start()
            await producer.start()
            log.info("이상탐지 스트림 시작: %s → %s", PRICE_TOPIC, ANOMALY_TOPIC)
            async for msg in consumer:
                await handle(detector, msg.value, r, producer)
        except KafkaConnectionError:
            log.info("Kafka 연결 대기 중...")
            await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - 로그 남기고 재시작
            log.exception("이상탐지 스트림 오류, 3초 후 재시작")
            await asyncio.sleep(3)
        finally:
            await consumer.stop()
            await producer.stop()


async def autosave(detector: StreamDetector, every_sec: int = 60) -> None:
    """학습된 모델을 주기적으로 볼륨에 저장"""
    while True:
        await asyncio.sleep(every_sec)
        n = await asyncio.to_thread(detector.registry.save_all)
        if n:
            log.info("모델 %d개 저장", n)
