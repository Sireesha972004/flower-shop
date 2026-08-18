from pathlib import Path


def generate_audio(text: str, chunk_id: str) -> str:
    """Create a placeholder audio file until a real TTS provider is configured."""
    filename = Path(f"{chunk_id}.mp3")
    filename.write_bytes(b"FAKE_AUDIO")
    return str(filename)
