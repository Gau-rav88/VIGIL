import jwt
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from vigil_common.config import get_settings
from vigil_common.timeutil import now_utc

app = FastAPI(title="Project VIGIL API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class DevTokenRequest(BaseModel):
    sub: str
    role: str = "compliance_officer"


@app.post("/api/v1/auth/dev-token")
async def issue_dev_token(req: DevTokenRequest) -> dict[str, str]:
    settings = get_settings()
    if settings.ENV == "prod":
        raise HTTPException(status_code=403, detail="Dev token issuance disabled in production")

    token = jwt.encode(
        {"sub": req.sub, "role": req.role, "iat": now_utc().timestamp()},
        settings.JWT_HS256_SECRET,
        algorithm="HS256"
    )
    return {"token": token}


@app.get("/api/v1/cases")
async def list_cases(limit: int = 50, symbol: str | None = None, status: str | None = None) -> dict[str, list]:
    return {"items": []}


@app.get("/api/v1/symbols/heatmap")
async def get_heatmap() -> list:
    return []
