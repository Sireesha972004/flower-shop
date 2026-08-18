from pathlib import Path

AUDIO_DIR = Path("audio")
DEFAULT_VOICE = "en-US-JennyNeural"
EDGE_VOICES = {
    "English Professional Reader": "en-US-JennyNeural",
    "Foreign Country Reader": "en-GB-SoniaNeural",
    "Hindi Reader": "hi-IN-SwaraNeural",
    "Tamil Reader": "ta-IN-PallaviNeural",
    "Telugu Reader": "te-IN-ShrutiNeural",
    "Kannada Reader": "kn-IN-SapnaNeural",
}


def audio_path(chunk_id: str) -> Path:
    AUDIO_DIR.mkdir(exist_ok=True)
    return AUDIO_DIR / f"{chunk_id}.mp3"


async def generate_audio_file(text: str, chunk_id: str, voice: str) -> str:
    import asyncio

    from edge_tts import Communicate

    path = audio_path(chunk_id)
    await asyncio.wait_for(
        Communicate(text, EDGE_VOICES.get(voice, DEFAULT_VOICE)).save(str(path)),
        timeout=45,
    )
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError("Audio file was not created.")
    return str(path)
