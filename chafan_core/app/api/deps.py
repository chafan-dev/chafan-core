from typing import Generator, Optional

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

from chafan_core.app import schemas, security
from chafan_core.app.config import settings
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.utils.base import HTTPException_, unwrap

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)

try_reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token", auto_error=False
)


def get_current_user_id(token: str = Depends(reusable_oauth2)) -> int:
    try:
        payload = jwt.decode(
            token, unwrap(settings.SECRET_KEY), algorithms=[security.ALGORITHM]
        )
        token_data = schemas.TokenPayload(**payload)
    except Exception:
        raise HTTPException_(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    if token_data.sub is None:
        raise HTTPException_(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )
    return token_data.sub


def try_get_current_user_id(
    token: Optional[str] = Depends(try_reusable_oauth2),
) -> Optional[int]:
    if token is None:
        return None
    try:
        return get_current_user_id(token)
    except Exception:
        return None


def get_request_context(
    current_user_id: Optional[int] = Depends(try_get_current_user_id),
) -> Generator:
    """Per-request context. Commits on success; rolls back on error."""
    ctx = RequestContext(principal_id=current_user_id)
    try:
        yield ctx
        ctx.commit()
    except Exception:
        ctx.rollback()
        raise
    finally:
        ctx.close()


def get_request_context_logged_in(
    current_user_id: int = Depends(get_current_user_id),
) -> Generator:
    ctx = RequestContext(principal_id=current_user_id)
    try:
        yield ctx
        ctx.commit()
    except Exception:
        ctx.rollback()
        raise
    finally:
        ctx.close()


def get_db() -> Generator:
    """Plain DB session. Commits on success; rolls back on error."""
    ctx = RequestContext()
    try:
        yield ctx.get_db()
        ctx.commit()
    except Exception:
        ctx.rollback()
        raise
    finally:
        ctx.close()
