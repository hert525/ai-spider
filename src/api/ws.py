"""WebSocket endpoints."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

router = APIRouter()


@router.websocket("/ws/generate")
async def ws_generate(ws: WebSocket):
    """Stream code generation via WebSocket."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            description = data.get("description", "")
            target_url = data.get("target_url", "")
            mode = data.get("mode", "code_generator")

            await ws.send_json({"type": "start", "mode": mode})

            try:
                if mode == "smart_scraper":
                    from src.engine.graphs import SmartScraperGraph
                    graph = SmartScraperGraph()
                    state = await graph.run(target_url, description)
                    extracted = state.get("extracted_data", [])
                    await ws.send_json({"type": "done", "mode": mode, "data": extracted})
                else:
                    from src.engine.graphs import CodeGeneratorGraph
                    graph = CodeGeneratorGraph()
                    state = await graph.run(target_url, description)
                    code = state.get("generated_code", "")
                    v_status = state.get("validation_status", "unknown")
                    await ws.send_json({
                        "type": "done",
                        "mode": mode,
                        "code": code,
                        "validation_status": v_status,
                    })
            except Exception as e:
                logger.error(f"WS generation error: {e}")
                await ws.send_json({"type": "error", "error": str(e)})

    except WebSocketDisconnect:
        pass


@router.websocket("/ws/stream")
async def ws_stream(ws: WebSocket):
    """Stream LLM responses for chat/refine."""
    await ws.accept()
    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action", "")

            if action == "chat":
                messages = data.get("messages", [])
                from litellm import acompletion
                from src.core.config import settings

                params = settings.get_llm_params()
                resp = await acompletion(
                    **params,
                    messages=messages,
                    stream=True,
                )
                async for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        await ws.send_json({"type": "chunk", "content": delta.content})
                await ws.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
