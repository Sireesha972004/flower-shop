import os

from minio import Minio


BUCKET = os.getenv("MINIO_BUCKET", "vox-audio")
client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
)


def upload(file_path: str) -> None:
    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)
    client.fput_object(BUCKET, file_path, file_path)
