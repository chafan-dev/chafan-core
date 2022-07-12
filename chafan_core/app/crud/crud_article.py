import datetime
from typing import Any, Dict, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.crud.crud_activity import create_article_activity, upvote_article_activity
from chafan_core.app.models.article import Article, ArticleUpvotes
from chafan_core.app.schemas.article import ArticleCreate, ArticleUpdate
from chafan_core.app.search import es_search


class CRUDArticle(CRUDBase[Article, ArticleCreate, ArticleUpdate]):
    def create_with_author(
        self, db: Session, *, obj_in: ArticleCreate, author_id: int
    ) -> Article:
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        obj_in_data = jsonable_encoder(obj_in)
        article_column = crud.article_column.get_by_uuid(
            db, uuid=obj_in_data["article_column_uuid"]
        )
        assert article_column is not None
        obj_in_data["article_column_id"] = article_column.id
        del obj_in_data["article_column_uuid"]
        del obj_in_data["writing_session_uuid"]
        if obj_in.is_published:
            obj_in_data["updated_at"] = utc_now

        del obj_in_data["content"]
        obj_in_data["body"] = obj_in.content.source
        obj_in_data["body_text"] = obj_in.content.rendered_text
        obj_in_data["editor"] = obj_in.content.editor

        db_obj = self.model(
            **obj_in_data,
            author_id=author_id,
            created_at=utc_now,
            uuid=self.get_unique_uuid(db)
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        db.add(create_article_activity(article=db_obj, created_at=utc_now,))
        db.commit()
        return db_obj

    def search(self, db: Session, *, q: str) -> List[Article]:
        ids = es_search("article", query=q)
        if not ids:
            return []
        ret = []
        for id in ids:
            article = self.get(db, id=id)
            if article:
                ret.append(article)
        return ret

    def update_topics(
        self, db: Session, *, db_obj: Article, new_topics: List[models.Topic]
    ) -> Article:
        db_obj.topics.clear()
        db_obj.topics = new_topics
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def upvote(self, db: Session, *, db_obj: Article, voter: models.User) -> Article:
        article_upvote = (
            db.query(ArticleUpvotes)
            .filter_by(article_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if article_upvote is None:
            article_upvote = ArticleUpvotes(article=db_obj, voter=voter)
            db.add(article_upvote)
            db_obj.upvotes_count += 1
            db.commit()
            db.refresh(db_obj)
            db.add(
                upvote_article_activity(
                    voter=voter,
                    article=db_obj,
                    created_at=datetime.datetime.now(tz=datetime.timezone.utc),
                )
            )
            db.commit()
        elif article_upvote.cancelled:
            db_obj.upvotes_count += 1
            article_upvote.cancelled = False
            db.commit()
        return db_obj

    def cancel_upvote(
        self, db: Session, *, db_obj: Article, voter: models.User
    ) -> Article:
        article_upvote = (
            db.query(ArticleUpvotes)
            .filter_by(article_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if article_upvote is not None and not article_upvote.cancelled:
            db_obj.upvotes_count -= 1
            assert db_obj.upvotes_count >= 0
            article_upvote.cancelled = True
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def delete_forever(self, db: Session, *, article: Article) -> None:
        article.is_deleted = True
        article.body = "[DELETED]"
        article.body_draft = "[DELETED]"
        for archive in article.archives:
            archive.body = "[DELETED]"
        db.add(article)
        db.commit()

    def update_checked(
        self, db: Session, *, db_obj: Article, obj_in: Dict[str, Any]
    ) -> Article:
        if db_obj.is_published and "is_published" in obj_in:
            assert obj_in["is_published"]
        return self.update(db, db_obj=db_obj, obj_in=obj_in)

    def get_all_published(self, db: Session) -> List[Article]:
        return db.query(Article).filter_by(is_deleted=False, is_published=True).all()

    def get_all(self, db: Session) -> List[Article]:
        return db.query(Article).all()


article = CRUDArticle(Article)
