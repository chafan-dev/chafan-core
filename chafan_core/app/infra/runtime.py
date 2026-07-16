"""Session/context runners for background and scheduled work."""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from sqlalchemy.orm.session import Session

from chafan_core.app.common import handle_exception
from chafan_core.app.infra.request_context import RequestContext

T = TypeVar("T")


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


def execute_with_context(
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
        if ctx.db is not None:
            if not ctx._committed:
                ctx.close()
            else:
                ctx._db.close()  # type: ignore[union-attr]
                ctx._db = None
    return None


# Historical name used across feed/task/scheduled.
execute_with_broker = execute_with_context
