import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routes import (
    auth,
    customers,
    members,
    repertoire,
    events,
    attendance,
    practice,
    arrangements,
    harmony,
    exports,
    rehearsal_tracks,
    sheet_music,
)

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Choir Director API started")
    yield


app = FastAPI(
    title="Choir Director API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(customers.router, prefix="/api/v1/customers", tags=["customers"])
app.include_router(members.router, prefix="/api/v1/members", tags=["members"])
app.include_router(repertoire.router, prefix="/api/v1/repertoire", tags=["repertoire"])
app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
app.include_router(attendance.router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(practice.router, prefix="/api/v1/practice", tags=["practice"])
app.include_router(arrangements.router, prefix="/api/v1/arrangements", tags=["arrangements"])
app.include_router(harmony.router, prefix="/api/v1/harmony", tags=["harmony"])
app.include_router(exports.router, prefix="/api/v1/exports", tags=["exports"])
app.include_router(rehearsal_tracks.router, prefix="/api/v1/rehearsal-tracks", tags=["rehearsal-tracks"])
app.include_router(sheet_music.router, prefix="/api/v1/sheet-music", tags=["sheet-music"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/")
async def root():
    return {
        "message": "Welcome to Choir Director API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
