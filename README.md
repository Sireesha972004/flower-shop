# Vox

Vox consists of a FastAPI service that queues text chunks and a Python worker that creates and uploads the resulting audio.

## Run

1. Start Docker Desktop, then run `docker compose up -d`.
2. In one terminal, run `venv\\Scripts\\uvicorn.exe app.main:app --port 5000`.
3. In another terminal, run `venv\\Scripts\\python.exe -m worker.main`.

Submit a job with:

```powershell
Invoke-RestMethod -Method Post http://localhost:5000/api/chunks -ContentType application/json -Body '{"text":"Hello from Vox"}'
```

The worker uploads the generated file to MinIO at http://localhost:9001.
