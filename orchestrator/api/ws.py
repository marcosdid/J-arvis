from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    broadcaster = websocket.app.state.ws_broadcaster
    if broadcaster is None:  # pragma: no cover
        await websocket.close(code=1011)
        return
    await websocket.accept()
    broadcaster.subscribe(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        broadcaster.unsubscribe(websocket)
