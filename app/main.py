import json
import os
from pathlib import Path
from threading import Lock
from uuid import uuid4

import redis
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


app = FastAPI(title="Vox API")
QUEUE_NAME = os.getenv("QUEUE_NAME", "vox")
USERS_PATH = Path("users.json")
password_hasher = PasswordHasher()
users_lock = Lock()
tokens: dict[str, str] = {}
chunks: dict[str, dict[str, str]] = {}
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    decode_responses=True,
)


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


def load_users() -> dict[str, dict[str, str] | str]:
    if not USERS_PATH.exists():
        return {}
    return json.loads(USERS_PATH.read_text(encoding="utf-8"))


def save_users(users: dict[str, dict[str, str] | str]) -> None:
    USERS_PATH.write_text(json.dumps(users, indent=2), encoding="utf-8")


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


@app.get("/health")
def health() -> dict[str, str]:
    redis_client.ping()
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
    users = load_users()
    password_hash = get_password_hash(users.get(email))
    if not password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
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
        if not record:
            raise HTTPException(status_code=404, detail="No account found for this email.")
        if isinstance(record, dict):
            record["password_hash"] = password_hasher.hash(body.password)
            users[email] = record
        else:
            users[email] = password_hasher.hash(body.password)
        save_users(users)
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


@app.post("/api/chunks", status_code=202)
def create_chunk(chunk: ChunkRequest, email: str = Depends(current_email)) -> dict[str, str]:
    chunk_id = chunk.chunk_id or str(uuid4())
    redis_client.rpush(QUEUE_NAME, json.dumps({"chunkId": chunk_id, "text": chunk.text}))
    chunks[chunk_id] = {
        "chunkId": chunk_id,
        "email": email,
        "title": chunk.title or chunk.text[:48],
        "voice": chunk.voice,
        "text": chunk.text,
        "status": "queued",
    }
    return {"chunkId": chunk_id, "status": "queued"}


@app.post("/api/chunk-ready")
def chunk_ready(chunk: ChunkReady) -> dict[str, str]:
    chunks[chunk.chunk_id] = {**chunks.get(chunk.chunk_id, {}), "chunkId": chunk.chunk_id, "status": "ready"}
    return {"chunkId": chunk.chunk_id, "status": "ready"}


@app.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: str, email: str = Depends(current_email)) -> dict[str, str]:
    job = chunks.get(chunk_id)
    if not job or job.get("email") != email:
        return {"chunkId": chunk_id, "status": "unknown"}
    return job


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
