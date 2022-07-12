import random
import time
from contextlib import contextmanager
from typing import Any

from chafan_core.app import crud
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.metrics.metrics_client import metrics_client_batch
from chafan_core.app.recs.indexing import (
    interesting_questions_indexer,
    interesting_users_indexer,
)
from chafan_core.app.task_utils import execute_with_broker


@contextmanager
def measure_duration(metric_name: str) -> Any:
    now = time.time()
    try:
        yield None
    finally:
        print(f"*** {metric_name}_duration_seconds: %.2f" % (time.time() - now))


def eval_retrive_user_data() -> None:
    def f(broker: DataBroker) -> None:
        with measure_duration("sample_users"):
            all_users = list(crud.user.get_all_active_users(broker.get_db()))
            all_users.sort(key=lambda u: u.karma, reverse=True)
            sample_users = random.sample(all_users[:100], 10)
        for u in sample_users:
            print("Removing user data...")
            interesting_users_indexer.delete_user_data(u.id)
            with measure_duration("retrive_user_data_empty_users"):
                interesting_users_indexer.retrive_user_data(
                    CachedLayer(broker, u.id), metrics_client_batch
                )
            with measure_duration("retrive_user_data_empty_questions"):
                interesting_questions_indexer.retrive_user_data(
                    CachedLayer(broker, u.id), metrics_client_batch
                )
            with measure_duration("retrive_user_data_existing_users"):
                interesting_users_indexer.retrive_user_data(
                    CachedLayer(broker, u.id), metrics_client_batch
                )
            with measure_duration("retrive_user_data_existing_questions"):
                interesting_questions_indexer.retrive_user_data(
                    CachedLayer(broker, u.id), metrics_client_batch
                )
            with measure_duration("get_follers"):
                CachedLayer(broker, u.id).get_followers(u, skip=0, limit=20)
            with measure_duration("get_followed"):
                CachedLayer(broker, u.id).get_followed(u, skip=0, limit=20)

    execute_with_broker(f, use_read_replica=True)


if __name__ == "__main__":
    print("Running offline metrics eval")
    eval_retrive_user_data()
