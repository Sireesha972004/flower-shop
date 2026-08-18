import json
from io import BytesIO
from pathlib import Path
from threading import Lock
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import BackgroundTasks, Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.tts import AUDIO_DIR, generate_audio_file


app = FastAPI(title="Vox API")
ROOT_DIR = Path(__file__).resolve().parent.parent
USERS_PATH = ROOT_DIR / "users.json"
JOBS_PATH = ROOT_DIR / "jobs.json"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
password_hasher = PasswordHasher()
users_lock = Lock()
jobs_lock = Lock()
tokens: dict[str, str] = {}
chunks: dict[str, dict[str, str]] = {}
users_db: dict[str, dict[str, str] | str] = {}
AUDIO_DIR.mkdir(exist_ok=True)


class ChunkRequest(BaseModel):
    text: str = Field(min_length=1)
    title: str = ""
    voice: str = "Hindi Reader"
    chunk_id: str | None = Field(default=None, alias="chunkId")


class ChunkReady(BaseModel):
    chunk_id: str = Field(alias="chunkId")


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    email: str = Field(min_length=3)
    password: str = Field(min_length=12)


class ResetPasswordRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=12)


def persist_users() -> None:
    try:
        USERS_PATH.write_text(json.dumps(users_db, indent=2), encoding="utf-8")
    except OSError as error:
        print(f"Could not save users: {error}")


def load_users() -> dict[str, dict[str, str] | str]:
    return users_db


def save_users(users: dict[str, dict[str, str] | str]) -> None:
    if users is not users_db:
        users_db.clear()
        users_db.update(users)
    persist_users()


def init_users() -> None:
    if not USERS_PATH.exists():
        return
    try:
        stored = json.loads(USERS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if isinstance(stored, dict):
        users_db.update(stored)


def ensure_user(email: str, password: str, username: str = "") -> dict[str, str]:
    record = users_db.get(email)
    if isinstance(record, dict) and not username:
        username = record.get("username", "").strip()
    users_db[email] = {
        "username": username or email.split("@")[0],
        "password_hash": password_hasher.hash(password),
    }
    persist_users()
    return users_db[email]


def load_chunks() -> None:
    if not JOBS_PATH.exists():
        return
    try:
        stored = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if isinstance(stored, dict):
        chunks.update(stored)


def persist_chunks() -> None:
    JOBS_PATH.write_text(json.dumps(chunks, indent=2), encoding="utf-8")


def upsert_job(chunk_id: str, **fields: str) -> dict[str, str]:
    with jobs_lock:
        job = {**chunks.get(chunk_id, {}), **fields, "chunkId": chunk_id}
        job["audioUrl"] = f"/audio/{chunk_id}.mp3"
        chunks[chunk_id] = job
        persist_chunks()
        return job


def get_password_hash(record: dict[str, str] | str | None) -> str | None:
    if isinstance(record, str):
        return record
    if isinstance(record, dict):
        return record.get("password_hash")
    return None


def normalize_email(email: str) -> str:
    value = email.strip().lower()
    if "@" not in value or "." not in value.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Enter a valid email address.")
    return value


def current_email(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in required.")
    email = tokens.get(authorization.split(" ", 1)[1])
    if not email:
        raise HTTPException(status_code=401, detail="Sign in required.")
    return email


def issue_token(email: str) -> dict[str, str]:
    token = str(uuid4())
    tokens[token] = email
    users = load_users()
    record = users.get(email)
    username = ""
    if isinstance(record, dict):
        username = record.get("username", "").strip()
    return {"token": token, "email": email, "username": username}


async def process_chunk(chunk_id: str, text: str, voice: str) -> None:
    try:
        await generate_audio_file(text, chunk_id, voice)
        upsert_job(chunk_id, status="ready")
    except Exception as error:
        upsert_job(chunk_id, status="failed", error="Could not generate audio.")
        print(f"Audio generation failed for {chunk_id}: {error}")


init_users()
load_chunks()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/register")
def register(body: RegisterRequest) -> dict[str, str]:
    email = normalize_email(body.email)
    username = body.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")
    with users_lock:
        users = load_users()
        if email in users:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        users[email] = {
            "username": username,
            "password_hash": password_hasher.hash(body.password),
        }
        save_users(users)
    return issue_token(email)


@app.post("/api/login")
def login(body: LoginRequest) -> dict[str, str]:
    email = normalize_email(body.email)
    password_hash = get_password_hash(users_db.get(email))
    if not password_hash:
        # Render's disk is ephemeral, so accounts disappear after a restart.
        # Recreate the account on sign-in when the password meets register rules.
        if len(body.password) < 12:
            raise HTTPException(
                status_code=401,
                detail="No account found. Please register with a password of at least 12 characters.",
            )
        with users_lock:
            if not get_password_hash(users_db.get(email)):
                ensure_user(email, body.password)
        return issue_token(email)
    try:
        password_hasher.verify(password_hash, body.password)
    except VerifyMismatchError as error:
        raise HTTPException(status_code=401, detail="Invalid email or password.") from error
    return issue_token(email)


@app.post("/api/forgot-password")
def forgot_password(body: ResetPasswordRequest) -> dict[str, str]:
    email = normalize_email(body.email)
    with users_lock:
        users = load_users()
        record = users.get(email)
        username = ""
        if isinstance(record, dict):
            username = record.get("username", "").strip()
        ensure_user(email, body.password, username)
    return {"message": "Password updated. You can sign in now.", "email": email}


@app.get("/api/me")
def me(email: str = Depends(current_email)) -> dict[str, str]:
    users = load_users()
    record = users.get(email)
    username = ""
    if isinstance(record, dict):
        username = record.get("username", "").strip()
    return {"email": email, "username": username}


@app.get("/api/library")
def library(email: str = Depends(current_email)) -> list[dict[str, str]]:
    return [job for job in chunks.values() if job.get("email") == email]


@app.post("/api/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    _email: str = Depends(current_email),
) -> dict[str, str]:
    filename = file.filename or "upload"
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Use a file under 5 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
        except Exception as error:
            raise HTTPException(status_code=400, detail="Could not read this PDF.") from error
        if not text:
            raise HTTPException(status_code=400, detail="Could not extract text from this PDF.")
    else:
        text = data.decode("utf-8", errors="ignore").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Could not read text from this file.")

    return {"title": Path(filename).stem, "text": text[:8000]}


@app.post("/api/chunks", status_code=202)
async def create_chunk(
    chunk: ChunkRequest,
    background_tasks: BackgroundTasks,
    email: str = Depends(current_email),
) -> dict[str, str]:
    chunk_id = chunk.chunk_id or str(uuid4())
    job = upsert_job(
        chunk_id,
        email=email,
        title=chunk.title or chunk.text[:48],
        voice=chunk.voice,
        text=chunk.text,
        status="queued",
    )
    background_tasks.add_task(process_chunk, chunk_id, chunk.text, chunk.voice)
    return job


@app.post("/api/chunk-ready")
def chunk_ready(chunk: ChunkReady) -> dict[str, str]:
    return upsert_job(chunk.chunk_id, status="ready")


@app.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: str, email: str = Depends(current_email)) -> dict[str, str]:
    job = chunks.get(chunk_id)
    if not job or job.get("email") != email:
        return {"chunkId": chunk_id, "status": "unknown"}
    return job


app.mount("/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
