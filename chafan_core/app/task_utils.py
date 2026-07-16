from typing import Callable, Optional, TypeVar

from sqlalchemy.orm.session import Session

from chafan_core.app.common import handle_exception
from chafan_core.app.infra.request_context import RequestContext

T = TypeVar("T")

# TODO This file should be removed. These patterns provide little benefit today 2025-Jul-11


def execute_with_db(
    db: Session, runnable: Callable[[Session], T], auto_commit: bool = True
) -> Optional[T]:
    try:
        ret = runnable(db)
        if auto_commit:
            db.commit()
        return ret
    except Exception as e:
        handle_exception(e)
    finally:
        db.close()
    return None


def execute_with_broker(
    runnable: Callable[[RequestContext], T],
    auto_commit: bool = True,
) -> Optional[T]:
    ctx = RequestContext()
    try:
        ret = runnable(ctx)
        if auto_commit and ctx.db is not None:
            ctx.db.commit()
            ctx.mark_committed()
        return ret
    except Exception as e:
        handle_exception(e)
    finally:
        if ctx.db is not None and not ctx._committed:
            ctx.close()
        elif ctx.db is not None:
            ctx._db.close()
            ctx._db = None
    return None
