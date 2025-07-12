"""
Redis-based API server with SSE for real-time updates
This FastAPI application connects to a Redis instance to listen for updates on a specific channel.
It provides an endpoint to get the current state stored in Redis and another endpoint to stream updates via
Server-Sent Events (SSE).
It uses the `sse_starlette` library for handling SSE and `redis.asyncio` for asynchronous Redis operations.

kubectl rollout restart -n default deployment apiserver
"""
import asyncio
import json
import logging

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from redis.asyncio import Redis

from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

redis = Redis.from_url(config['redis_url'], decode_responses=True)
UPDATE_CHANNEL = config['update_channel']

sse_clients = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event to initialize Redis connection and start the listener.
    """
    task = asyncio.create_task(redis_listener())
    yield
    task.cancel()  # Cancel the listener task when the app shuts down

    try:
        await task  # Check if Redis is reachable
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)    

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],  # for local testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/key/Environment")
async def get_current_environment():
    logging.info(f"Fetching Redis key: environment")
    weatherval = await redis.get("Weather")
    aqival = await redis.get("AQI")
    moonval = await redis.get("Moon")
    val = {
        'AQI'    : json.loads(aqival or '{}'),
        'Moon'   : json.loads(moonval or '{}'),
        'Weather': json.loads(weatherval or '{}')
    }
    return JSONResponse(content=val)

@app.get("/key/{KV_KEY}")
async def get_current_state(KV_KEY: str):
    logging.info(f"Fetching Redis key: {KV_KEY}")
    val = await redis.get(str(KV_KEY))
    return JSONResponse(content=json.loads(val or '{}'))

async def broadcast(payload: dict):
    msg = json.dumps(payload)
    for q in list(sse_clients):
        await q.put(msg)

@app.put("/webcontrol/{command}")
async def send_webcontrol_command(command: str):
    valid_commands = {'pp', 'fwd', 'rew', 'out'}
    if command not in valid_commands:
        return JSONResponse(status_code=400, content={"error": "Invalid command"})

    payload = {
        "type": "webcontrol",
        "command": command
    }

    await broadcast(payload)
    return JSONResponse(status_code=202, content={"status": "Command queued"})

@app.get("/events")
async def stream_events(request: Request):
    logging.info("Client connected for SSE updates")
    queue = asyncio.Queue()
    sse_clients.append(queue)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await queue.get()
                yield {"event": "update", "data": msg}
        finally:
            sse_clients.remove(queue)

    return EventSourceResponse(event_generator())

async def redis_listener():
    pubsub = redis.pubsub()
    await pubsub.subscribe(UPDATE_CHANNEL)

    async for message in pubsub.listen():
        if message["type"] == "message":
            data = message["data"]
            # Broadcast to all connected clients
            for q in list(sse_clients):
                await q.put(data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apiserver:app", host="0.0.0.0", port=8000, reload=True)
