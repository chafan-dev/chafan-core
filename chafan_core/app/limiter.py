from slowapi import Limiter

from chafan_core.app.common import client_ip, enable_rate_limit, get_redis_cli
from chafan_core.app.config import settings

limiter = Limiter(
    key_func=client_ip,
    headers_enabled=True,
    default_limits=["150/minute"],
    storage_uri=settings.REDIS_URL,
    key_prefix="chafan:slowapi:",
    enabled=enable_rate_limit(),
)


def clear_limits_for_ip(ip: str) -> None:
    redis = get_redis_cli()
    for key in redis.scan_iter(f"LIMITER/chafan:slowapi:/{ip}/*"):
        limiter._storage.clear(key)
