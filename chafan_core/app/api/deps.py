from typing import Any, Generator, Optional

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

from chafan_core.app import schemas, security
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.config import settings
from chafan_core.app.data_broker import DataBroker
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


def get_data_broker_with_params(*, use_read_replica: bool = False) -> Any:
    def _f() -> Generator:
        try:
            broker = DataBroker(use_read_replica=use_read_replica)
            yield broker
        finally:
            broker.close()

    return _f


def get_cached_layer(
    current_user_id: Optional[int] = Depends(try_get_current_user_id),
) -> Generator:
    try:
        broker = DataBroker()
        yield CachedLayer(broker, current_user_id)
    finally:
        broker.close()


def get_cached_layer_logged_in(
    current_user_id: int = Depends(get_current_user_id),
    broker: DataBroker = Depends(get_data_broker_with_params()),
) -> Generator:
    yield CachedLayer(broker, current_user_id)


def get_db(
    broker: DataBroker = Depends(get_data_broker_with_params()),
) -> Generator:
    yield broker.get_db()


def get_read_db(
    broker: DataBroker = Depends(get_data_broker_with_params(use_read_replica=True)),
) -> Generator:
    yield broker.get_db()
