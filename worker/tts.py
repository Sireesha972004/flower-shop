from app.tts import generate_audio_file


def generate_audio(text: str, chunk_id: str) -> str:
    import asyncio

    return asyncio.run(generate_audio_file(text, chunk_id, "English Professional Reader"))
