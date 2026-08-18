import json
import os

import redis


QUEUE_NAME = os.getenv("QUEUE_NAME", "vox")
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
)


def listen():
    print(f"Worker started. Waiting for jobs on '{QUEUE_NAME}'...")
    while True:
        _, message = redis_client.blpop(QUEUE_NAME)
        yield json.loads(message)
