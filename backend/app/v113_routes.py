from __future__ import annotations

from fastapi import APIRouter

from .run_v113_health import build_health


router = APIRouter(
    prefix="/v113",
    tags=["v113"],
)


@router.get("/health")
def health():
    return build_health()
