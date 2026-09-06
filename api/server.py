"""
PHANTOM FastAPI Backend Server
Runs on http://127.0.0.1:8747
Provides REST and WebSocket endpoints for the web UI.
"""
from __future__ import annotations
import asyncio
import json
import sys
import uuid
from contextlib import asynccontextmanager

# Windows consoles often default to cp1252/cp437; a stray smart quote or
# em-dash in a logged LLM response would otherwise crash a print() call.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm model on startup
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _prewarm)
    yield


def _prewarm():
    try:
        from phantom_graph import prewarm_ollama, prewarm_pipeline
        prewarm_ollama()
        prewarm_pipeline()
    except Exception as e:
        print(f'[SERVER] Pre-warm failed: {e}')


app = FastAPI(title='PHANTOM API', version='1.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/health')
async def health():
    return {'status': 'ok', 'version': '1.0'}


@app.get('/status')
async def status():
    """
    Live provider dashboard: 24h usage (file-backed, survives restarts and
    includes traffic from BOTH the graph path and the router) plus current
    rate-window state per provider.

    Caveat: `providers` is this process's in-memory router state. Requests
    served through phantom_graph's llm_call_node don't touch PhantomRouter,
    so their window counters stay at zero here — `usage_24h` is the number
    that reflects all real traffic.
    """
    from llm_router import get_router
    router = get_router()
    return {
        'usage_24h': router.daily_summary(),
        'providers': router.status_all(),
    }


@app.post('/query')
async def query_endpoint(body: dict):
    q = body.get('query', '')
    tid = body.get('thread_id', str(uuid.uuid4()))
    loop = asyncio.get_event_loop()
    from phantom_graph import run_query
    result = await loop.run_in_executor(None, lambda: run_query(q, thread_id=tid, verbose=False))
    return result


@app.post('/resume')
async def resume_endpoint(body: dict):
    decision = body.get('decision', 'reject')
    tid = body.get('thread_id', '')
    if not tid:
        return {'error': 'thread_id required'}
    loop = asyncio.get_event_loop()
    from phantom_graph import resume_query
    result = await loop.run_in_executor(None, lambda: resume_query(decision, tid))
    return result


@app.websocket('/stream')
async def stream_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        data = await ws.receive_json()
    except WebSocketDisconnect:
        return

    q = data.get('query', '')
    tid = data.get('thread_id', str(uuid.uuid4()))
    loop = asyncio.get_event_loop()

    # token_callback sends tokens live over WebSocket
    async def send_token(token: str):
        try:
            await ws.send_text(json.dumps({'type': 'token', 'content': token}))
        except Exception:
            pass

    def token_callback(token: str):
        asyncio.run_coroutine_threadsafe(send_token(token), loop)

    from phantom_graph import run_query
    try:
        result = await loop.run_in_executor(
            None,
            lambda: run_query(q, thread_id=tid, verbose=False, token_callback=token_callback)
        )
        await ws.send_text(json.dumps({'type': 'done', 'result': result}))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(json.dumps({'type': 'error', 'message': str(e)}))
        except Exception:
            pass


def start_server():
    """Start FastAPI server. Call from phantom_ui.py in a daemon thread."""
    uvicorn.run(app, host='127.0.0.1', port=8747, log_level='error')


if __name__ == '__main__':
    start_server()
