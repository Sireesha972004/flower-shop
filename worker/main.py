import asyncio
import os

import requests

from app.tts import generate_audio_file
from worker.queue import listen
from worker.storage import upload


API_CALLBACK = os.getenv("API_CALLBACK", "http://localhost:5000/api/chunk-ready")


def run() -> None:
    for job in listen():
        chunk_id = job["chunkId"]
        text = job["text"]
        voice = job.get("voice", "English Professional Reader")
        print(f"Processing chunk {chunk_id}")

        audio_file = asyncio.run(generate_audio_file(text, chunk_id, voice))
        upload(audio_file)
        requests.post(API_CALLBACK, json={"chunkId": chunk_id}, timeout=10).raise_for_status()


if __name__ == "__main__":
    run()
