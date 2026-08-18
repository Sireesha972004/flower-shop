import os

import requests

from worker.queue import listen
from worker.storage import upload
from worker.tts import generate_audio


API_CALLBACK = os.getenv("API_CALLBACK", "http://localhost:5000/api/chunk-ready")


def run() -> None:
    for job in listen():
        chunk_id = job["chunkId"]
        text = job["text"]
        print(f"Processing chunk {chunk_id}")

        audio_file = generate_audio(text, chunk_id)
        upload(audio_file)
        requests.post(API_CALLBACK, json={"chunkId": chunk_id}, timeout=10).raise_for_status()


if __name__ == "__main__":
    run()
