from typing import Optional

import redis
from sqlalchemy.orm import Session

from chafan_core.app.common import get_redis_cli
from chafan_core.db.session import ReadSessionLocal, SessionLocal


# Data broker operates after authentication logic and business logic
# Its main job is to manage cache and data backend sessions.
class DataBroker(object):
    def __init__(self, use_read_replica: bool = False) -> None:
        self.redis: Optional[redis.Redis] = None
        self.db: Optional[Session] = None
        self.use_read_replica = use_read_replica

    def get_redis(self) -> redis.Redis:
        if self.redis is None:
            self.redis = get_redis_cli()
        return self.redis

    def get_db(self) -> Session:
        if self.db is None:
            if self.use_read_replica:
                self.db = ReadSessionLocal()
            else:
                self.db = SessionLocal()
        return self.db

    def close(self) -> None:
        if self.db:
            if not self.use_read_replica:
                self.db.commit()
            self.db.close()
