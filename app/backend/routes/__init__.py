from .auth import router as auth_router
from .members import router as members_router
from .repertoire import router as repertoire_router
from .events import router as events_router
from .attendance import router as attendance_router
from .practice import router as practice_router
from .arrangements import router as arrangements_router
from .exports import router as exports_router
from .harmony import router as harmony_router
from .rehearsal_tracks import router as rehearsal_tracks_router
from .sheet_music import router as sheet_music_router
from .customers import router as customers_router

__all__ = [
    "auth_router",
    "members_router",
    "repertoire_router",
    "events_router",
    "attendance_router",
    "practice_router",
    "arrangements_router",
    "exports_router",
    "harmony_router",
    "rehearsal_tracks_router",
    "sheet_music_router",
    "customers_router",
]
