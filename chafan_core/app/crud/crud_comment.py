from typing import Callable, List

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.crud.base import CRUDBase
from chafan_core.app.models.comment import Comment
from chafan_core.app.schemas.comment import CommentCreate, CommentUpdate
from chafan_core.utils.base import get_utc_now, unwrap


class CRUDComment(CRUDBase[Comment, CommentCreate, CommentUpdate]):
    def create_with_author(
        self,
        db: Session,
        *,
        obj_in: CommentCreate,
        author_id: int,
        check_site: Callable[[models.Site], None]
    ) -> Comment:
        obj_in_data = jsonable_encoder(obj_in)
        if "question_uuid" in obj_in_data:
            if obj_in_data["question_uuid"]:
                question = unwrap(
                    crud.question.get_by_uuid(db, uuid=obj_in_data["question_uuid"])
                )
                check_site(question.site)
                obj_in_data["site_id"] = question.site.id
                obj_in_data["question_id"] = question.id
            del obj_in_data["question_uuid"]
        if "submission_uuid" in obj_in_data:
            if obj_in_data["submission_uuid"]:
                submission = unwrap(
                    crud.submission.get_by_uuid(db, uuid=obj_in_data["submission_uuid"])
                )
                check_site(submission.site)
                obj_in_data["site_id"] = submission.site.id
                obj_in_data["submission_id"] = submission.id
            del obj_in_data["submission_uuid"]
        if "answer_uuid" in obj_in_data:
            if obj_in_data["answer_uuid"]:
                answer = unwrap(
                    crud.answer.get_by_uuid(db, uuid=obj_in_data["answer_uuid"])
                )
                check_site(answer.site)
                obj_in_data["site_id"] = answer.site.id
                obj_in_data["answer_id"] = answer.id
            del obj_in_data["answer_uuid"]
        if "article_uuid" in obj_in_data:
            if obj_in_data["article_uuid"]:
                obj_in_data["article_id"] = crud.article.get_by_uuid(db, uuid=obj_in_data["article_uuid"]).id  # type: ignore
            del obj_in_data["article_uuid"]
        if "parent_comment_uuid" in obj_in_data:
            if obj_in_data["parent_comment_uuid"]:
                parent_comment = unwrap(
                    crud.comment.get_by_uuid(
                        db, uuid=obj_in_data["parent_comment_uuid"]
                    )
                )
                if parent_comment.site:
                    check_site(parent_comment.site)
                    obj_in_data["site_id"] = parent_comment.site.id
                obj_in_data["parent_comment_id"] = parent_comment.id
            del obj_in_data["parent_comment_uuid"]
        if "mentioned" in obj_in_data:
            del obj_in_data["mentioned"]
        if "content" in obj_in_data:
            obj_in_data["body"] = obj_in.content.source
            obj_in_data["body_text"] = obj_in.content.rendered_text
            obj_in_data["editor"] = obj_in.content.editor
            del obj_in_data["content"]
        utc_now = get_utc_now()
        db_obj = self.model(
            **obj_in_data,
            uuid=self.get_unique_uuid(db),
            author_id=author_id,
            created_at=utc_now,
            updated_at=utc_now
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete_forever(self, db: Session, *, comment: Comment) -> None:
        comment.is_deleted = True
        comment.body = "[DELETED]"
        comment.body_text = "[DELETED]"
        db.add(comment)
        db.commit()

    def upvote(self, db: Session, *, db_obj: Comment, voter: models.User) -> Comment:
        comment_upvote = (
            db.query(models.comment.CommentUpvotes)
            .filter_by(comment_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if comment_upvote is None:
            comment_upvote = models.comment.CommentUpvotes(comment=db_obj, voter=voter)
            db.add(comment_upvote)
            db_obj.upvotes_count += 1
            db.commit()
            db.refresh(db_obj)
        elif comment_upvote.cancelled:
            db_obj.upvotes_count += 1
            comment_upvote.cancelled = False
            db.commit()
        return db_obj

    def cancel_upvote(
        self, db: Session, *, db_obj: Comment, voter: models.User
    ) -> Comment:
        comment_upvote = (
            db.query(models.comment.CommentUpvotes)
            .filter_by(comment_id=db_obj.id, voter_id=voter.id)
            .first()
        )
        if comment_upvote is not None and not comment_upvote.cancelled:
            db_obj.upvotes_count -= 1
            assert db_obj.upvotes_count >= 0
            comment_upvote.cancelled = True
            db.commit()
            db.refresh(db_obj)
        return db_obj

    def get_all_valid(self, db: Session) -> List[Comment]:
        return db.query(Comment).filter_by(is_deleted=False).all()

    def get_all(self, db: Session) -> List[Comment]:
        return db.query(Comment).all()


comment = CRUDComment(Comment)
