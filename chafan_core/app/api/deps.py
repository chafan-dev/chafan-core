from typing import Any, Generator, Optional

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt

from chafan_core.app import schemas, security
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.config import settings
from chafan_core.app.data_broker import DataBroker
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
    """Preferred per-request context (principal + lazy db/redis).

    Yields a DataBroker (RequestContext subclass) so Materializer/CachedLayer
    can share the same instance when needed. close_legacy_commit keeps
    historical request-end commit until services own transactions.
    """
    ctx: RequestContext = DataBroker(principal_id=current_user_id)
    try:
        yield ctx
    finally:
        ctx.close_legacy_commit()


def get_request_context_logged_in(
    current_user_id: int = Depends(get_current_user_id),
) -> Generator:
    ctx: RequestContext = DataBroker(principal_id=current_user_id)
    try:
        yield ctx
    finally:
        ctx.close_legacy_commit()


def get_data_broker_with_params(*, use_read_replica: bool = False) -> Any:
    def _f() -> Generator:
        try:
            broker = DataBroker(use_read_replica=use_read_replica)
            yield broker
        finally:
            broker.close()

    return _f


def cached_layer_from_context(ctx: RequestContext) -> CachedLayer:
    """Build a transitional CachedLayer on a RequestContext/DataBroker.

    Prefer calling services with RequestContext directly. This helper exists
    only while responders/materializer still expect a CachedLayer façade.
    """
    broker = ctx if isinstance(ctx, DataBroker) else DataBroker(principal_id=ctx.principal_id)
    if not isinstance(ctx, DataBroker):
        broker._db = ctx._db
        broker._redis = ctx._redis
    return CachedLayer(broker, ctx.principal_id)


def get_db(
    broker: DataBroker = Depends(get_data_broker_with_params()),
) -> Generator:
    yield broker.get_db()


def get_read_db(
    broker: DataBroker = Depends(get_data_broker_with_params(use_read_replica=False)),
) -> Generator:
    # D6: no read replica — same session factory as get_db.
    yield broker.get_db()
