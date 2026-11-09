"""실시간 알림 WebSocket

자동매매 주문(engine)과 AI 이상탐지(ai 컨테이너)가 Redis 'alerts' 채널에 발행한 알림을
브라우저로 즉시 전달한다. (Redis Pub/Sub → WebSocket)
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
log = logging.getLogger("uvicorn.error")


@router.websocket("/ws/alerts")
async def alerts_ws(ws: WebSocket):
    await ws.accept()
    pubsub = ws.app.state.redis.pubsub()
    await pubsub.subscribe("alerts")

    async def forward():
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                await ws.send_text(msg["data"])

    async def wait_close():
        try:
            while True:
                await ws.receive_text()  # 클라이언트 ping 무시, 끊기면 예외
        except WebSocketDisconnect:
            pass

    tasks = [asyncio.create_task(forward()), asyncio.create_task(wait_close())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await pubsub.unsubscribe("alerts")
        await pubsub.aclose()
