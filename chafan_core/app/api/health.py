from typing import Any

from fastapi import APIRouter

from chafan_core.app import schemas

router = APIRouter()


@router.get("/", response_model=schemas.HealthResponse)
def get_health() -> Any:
    return schemas.HealthResponse()

@router.get("/health", response_model=schemas.HealthResponse)
def get_health_test() -> Any:
    return schemas.HealthResponse()
