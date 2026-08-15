from chafan_core.app import crud
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.utils.base import EntityType


def cache_matrices() -> None:
    """Warm recs matrices (in-process; content redis cache removed)."""

    def f(broker: RequestContext) -> None:
        from chafan_core.app.recs import matrices as recs_matrices

        db = broker.get_db()
        recs_matrices.compute_follow_follow_fanout(db)
        for t in EntityType._member_map_.values():
            recs_matrices.compute_entity_similarity_matrix(db, t)  # type: ignore
        for u in crud.user.get_all_active_users(db):
            recs_matrices.compute_user_contributions(u)

    execute_with_broker(f)
