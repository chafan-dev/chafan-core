import json
import random
from typing import Callable, Generic, List, Type, TypeVar, Union

from fastapi.encoders import jsonable_encoder
from pydantic.tools import parse_raw_as
from pymongo import UpdateOne  # type: ignore
from pymongo.database import Database as MongoDB  # type: ignore

from chafan_core.app import crud, models, schemas
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.common import get_mongo_db, is_dev
from chafan_core.app.data_broker import DataBroker
from chafan_core.app.materialize import get_active_site_profile
from chafan_core.app.recs.ranking import rank_user_previews
from chafan_core.app.schemas.preview import UserPreview
from chafan_core.utils.base import filter_not_none, unwrap

_MAX_SITE_INTERESTING_QUESTION_SIZE = 20


def compute_site_interesting_question_ids(site: models.Site) -> List[int]:
    """Baseline impl: randomly select batches * batch_size candidates"""
    qs = [q.id for q in site.questions if not q.is_hidden]
    if len(qs) > _MAX_SITE_INTERESTING_QUESTION_SIZE:
        qs = random.sample(qs, k=_MAX_SITE_INTERESTING_QUESTION_SIZE)
    return qs


_MAX_INTERESTING_QUESTION_PER_USER = 50


def compute_interesting_questions(
    cached_layer: CachedLayer,
    _: List[models.User],
) -> Union[List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]]:
    current_user_id = cached_layer.principal_id
    db = cached_layer.get_db()
    if current_user_id:
        current_user = crud.user.get(db, id=current_user_id)
        assert current_user is not None
        questions: List[schemas.QuestionPreview] = []
        for site in db.query(models.Site):
            if site.public_readable or get_active_site_profile(
                db, site=site, user_id=current_user.id
            ):
                qs = compute_site_interesting_question_ids(site)
                questions.extend(
                    filter_not_none(
                        [
                            cached_layer.materializer.preview_of_question(
                                unwrap(crud.question.get(db, id=q_id))
                            )
                            for q_id in qs
                        ]
                    )
                )
        if len(questions) <= _MAX_INTERESTING_QUESTION_PER_USER:
            return questions
        else:
            return random.sample(questions, _MAX_INTERESTING_QUESTION_PER_USER)
    else:
        questions_for_visitors: List[schemas.QuestionPreviewForVisitor] = []
        for site in crud.site.get_all_public_readable(db):
            qs = compute_site_interesting_question_ids(site)
            questions_for_visitors.extend(
                filter_not_none(
                    [
                        cached_layer.materializer.preview_of_question_for_visitor(
                            unwrap(crud.question.get(db, id=q_id))
                        )
                        for q_id in qs
                    ]
                )
            )
        return questions_for_visitors


def compute_interesting_users(
    cached_layer: CachedLayer, all_users: List[models.User]
) -> List[UserPreview]:
    current_user = cached_layer.try_get_current_user()
    if current_user:
        user_candidates = [
            cached_layer.preview_of_user(u)
            for u in all_users
            if u not in current_user.followed and u != current_user
        ]
    else:
        user_candidates = [cached_layer.preview_of_user(u) for u in all_users]
    return rank_user_previews(user_candidates)[:50]


T = TypeVar("T")


class Indexer(Generic[T]):
    def __init__(
        self,
        t: Type[T],
        key: str,
        compute: Callable[[CachedLayer, List[models.User]], T],
    ):
        self.t = t
        self.key = key
        self.compute = compute

    def index_user_data(
        self,
        cached_layer: CachedLayer,
        mongo: MongoDB,
        all_users: List[models.User],
    ) -> T:
        data = self.compute(cached_layer, all_users)
        mongo.user_data.update_one(
            {"principal_id": cached_layer.principal_id},
            {"$set": {self.key: json.dumps(jsonable_encoder(data))}},
            upsert=True,
        )
        return data

    def index_all_user_data(
        self, broker: DataBroker, mongo: MongoDB, all_users: List[models.User]
    ) -> None:
        mongo_ops = []
        for idx, u in enumerate(all_users):
            if idx % (len(all_users) // 10) == 0:
                print(f"Finished {idx}, total {len(all_users)}")
            cached_layer = CachedLayer(broker, u.id)
            data = self.compute(cached_layer, all_users)
            mongo_ops.append(
                UpdateOne(
                    {"principal_id": cached_layer.principal_id},
                    {"$set": {self.key: json.dumps(jsonable_encoder(data))}},
                    upsert=True,
                )
            )
        mongo.user_data.bulk_write(mongo_ops)

    def retrive_user_data(self, cached_layer: CachedLayer) -> T:
        if is_dev():
            all_users = crud.user.get_all_active_users(cached_layer.get_db())
            return self.compute(cached_layer, all_users)
        mongo = get_mongo_db()
        result = mongo.user_data.find_one(
            {"principal_id": cached_layer.principal_id}, {self.key: 1, "_id": 0}
        )
        if not result:
            all_users = crud.user.get_all_active_users(cached_layer.get_db())
            return self.index_user_data(cached_layer, mongo, all_users)
        return parse_raw_as(self.t, result[self.key])

    def delete_user_data(self, principal_id: int) -> None:
        mongo = get_mongo_db()
        mongo.user_data.delete_one({"principal_id": principal_id})


interesting_users_indexer = Indexer(
    List[UserPreview], "users", compute_interesting_users
)
interesting_questions_indexer = Indexer(
    Union[List[schemas.QuestionPreview], List[schemas.QuestionPreviewForVisitor]],  # type: ignore
    "questions",
    compute_interesting_questions,
)


def index_all_interesting_users(broker: DataBroker) -> None:
    print("Indexing all interesting users..", flush=True)
    mongo = get_mongo_db()
    all_users = crud.user.get_all_active_users(broker.get_db())
    interesting_users_indexer.index_all_user_data(broker, mongo, all_users)


def index_all_interesting_questions(broker: DataBroker) -> None:
    print("Indexing all interesting questions..", flush=True)
    mongo = get_mongo_db()
    all_users = crud.user.get_all_active_users(broker.get_db())
    for u in all_users:
        interesting_questions_indexer.index_user_data(
            CachedLayer(broker, u.id), mongo, all_users
        )
