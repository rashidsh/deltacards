from typing import Protocol

from starlette.websockets import WebSocket, WebSocketDisconnect


class SocketClosed(Exception):
    """Raised when the client WebSocket is no longer available."""


class GameSocket(Protocol):
    async def receive(self) -> str | bytes:
        ...

    async def send_text(self, text: str) -> None:
        ...

    async def close(
        self,
        *,
        code: int,
        reason: str,
    ) -> None:
        ...


class StarletteGameSocket:
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket

    async def receive(self) -> str | bytes:
        try:
            message = await self.websocket.receive()
        except WebSocketDisconnect as exc:
            raise SocketClosed from exc

        message_type = message['type']
        if message_type == 'websocket.disconnect':
            raise SocketClosed

        if message_type != 'websocket.receive':
            raise RuntimeError(f"Unexpected ASGI WebSocket message {message_type!r}")

        text = message.get('text')
        if text is not None:
            return text

        data = message.get('bytes')
        if data is not None:
            return data

        raise RuntimeError("WebSocket receive event contained no text or bytes")

    async def send_text(self, text: str) -> None:
        try:
            await self.websocket.send_text(text)
        except (WebSocketDisconnect, RuntimeError) as exc:
            raise SocketClosed from exc

    async def close(
        self,
        *,
        code: int,
        reason: str,
    ) -> None:
        try:
            await self.websocket.close(
                code=code,
                reason=reason,
            )
        except (WebSocketDisconnect, RuntimeError) as exc:
            raise SocketClosed from exc
