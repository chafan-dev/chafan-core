import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud, models
from chafan_core.app.schemas.report import ReportCreate
from chafan_core.app.schemas.user import UserCreate
from chafan_core.app.schemas.site import SiteCreate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.submission import SubmissionCreate
from chafan_core.app.schemas.answer import AnswerCreate
from chafan_core.app.schemas.comment import CommentCreate
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import ContentVisibility, ReportReason, get_uuid
from chafan_core.tests.utils.utils import (
    random_email,
    random_password,
    random_short_lower_string,
)


def _create_test_user(db: Session):
    """Helper to create a test user."""
    user_in = UserCreate(
        email=random_email(),
        password=random_password(),
        handle=random_short_lower_string(),
    )
    return asyncio.run(crud.user.create(db, obj_in=user_in))


def _create_test_site(db: Session, moderator):
    """Helper to create a test site."""
    site_in = SiteCreate(
        name=f"Test Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def _create_test_question(db: Session, author_id: int, site):
    """Helper to create a test question."""
    question_in = QuestionCreate(
        site_uuid=site.uuid,
        title=f"Test Question {random_short_lower_string()}",
    )
    return crud.question.create_with_author(db, obj_in=question_in, author_id=author_id)


def _create_test_submission(db: Session, author_id: int, site):
    """Helper to create a test submission."""
    submission_in = SubmissionCreate(
        site_uuid=site.uuid,
        title=f"Test Submission {random_short_lower_string()}",
        url="https://example.com/test",
    )
    return crud.submission.create_with_author(
        db, obj_in=submission_in, author_id=author_id
    )


def _create_test_answer(db: Session, author_id: int, question, site):
    """Helper to create a test answer."""
    answer_in = AnswerCreate(
        content=RichText(
            source="Test answer content",
            rendered_text="Test answer content",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
        is_published=True,
        visibility=ContentVisibility.ANYONE,
        writing_session_uuid=get_uuid(),
    )
    return crud.answer.create_with_author(
        db, obj_in=answer_in, author_id=author_id, site_id=site.id
    )


def _create_test_comment(db: Session, author_id: int, question):
    """Helper to create a test comment."""
    comment_in = CommentCreate(
        content=RichText(
            source="Test comment content",
            rendered_text="Test comment content",
            editor="tiptap",
        ),
        question_uuid=question.uuid,
    )
    return crud.comment.create_with_author(
        db, obj_in=comment_in, author_id=author_id, check_site=lambda s: None
    )


def _noop_check_site(site: models.Site) -> None:
    """No-op check_site callback for testing."""
    pass


def test_create_report_for_question(db: Session) -> None:
    """Test creating a report for a question."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)

    report_in = ReportCreate(
        question_uuid=question.uuid,
        submission_uuid=None,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.SPAM,
        reason_comment="This is spam",
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    assert report is not None
    assert report.author_id == reporter.id
    assert report.question_id == question.id
    assert report.reason == ReportReason.SPAM
    assert report.reason_comment == "This is spam"
    assert report.created_at is not None


def test_create_report_for_submission(db: Session) -> None:
    """Test creating a report for a submission."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    submission = _create_test_submission(db, author_id=author.id, site=site)

    report_in = ReportCreate(
        question_uuid=None,
        submission_uuid=submission.uuid,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.OFF_TOPIC,
        reason_comment="Off topic content",
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    assert report is not None
    assert report.submission_id == submission.id
    assert report.reason == ReportReason.OFF_TOPIC


def test_create_report_for_answer(db: Session) -> None:
    """Test creating a report for an answer."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)
    answer = _create_test_answer(db, author_id=author.id, question=question, site=site)

    report_in = ReportCreate(
        question_uuid=None,
        submission_uuid=None,
        answer_uuid=answer.uuid,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.RUDE_OR_ABUSIVE,
        reason_comment="Rude language",
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    assert report is not None
    assert report.answer_id == answer.id
    assert report.reason == ReportReason.RUDE_OR_ABUSIVE


def test_create_report_for_comment(db: Session) -> None:
    """Test creating a report for a comment."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)
    comment = _create_test_comment(db, author_id=author.id, question=question)

    report_in = ReportCreate(
        question_uuid=None,
        submission_uuid=None,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=comment.uuid,
        reason=ReportReason.NEEDS_IMPROVEMENT,
        reason_comment="Low quality",
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    assert report is not None
    assert report.comment_id == comment.id
    assert report.reason == ReportReason.NEEDS_IMPROVEMENT


def test_create_report_without_reason_comment(db: Session) -> None:
    """Test creating a report without a reason comment."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)

    report_in = ReportCreate(
        question_uuid=question.uuid,
        submission_uuid=None,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.DUPLICATE,
        reason_comment=None,
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    assert report is not None
    assert report.reason == ReportReason.DUPLICATE
    assert report.reason_comment is None


def test_get_all_reports(db: Session) -> None:
    """Test getting all reports."""
    initial_count = len(crud.report.get_all(db))

    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)

    report_in = ReportCreate(
        question_uuid=question.uuid,
        submission_uuid=None,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.SPAM,
        reason_comment="Test report",
    )

    crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    all_reports = crud.report.get_all(db)
    assert len(all_reports) == initial_count + 1


def test_get_report_by_id(db: Session) -> None:
    """Test getting a report by ID."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)
    question = _create_test_question(db, author_id=author.id, site=site)

    report_in = ReportCreate(
        question_uuid=question.uuid,
        submission_uuid=None,
        answer_uuid=None,
        article_uuid=None,
        comment_uuid=None,
        reason=ReportReason.SPAM,
        reason_comment="Test report",
    )

    report = crud.report.create_with_author(
        db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
    )

    retrieved_report = crud.report.get(db, id=report.id)
    assert retrieved_report is not None
    assert retrieved_report.id == report.id


def test_get_report_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent report."""
    result = crud.report.get(db, id=99999999)
    assert result is None


def test_different_report_reasons(db: Session) -> None:
    """Test creating reports with different reasons."""
    author = _create_test_user(db)
    reporter = _create_test_user(db)
    site = _create_test_site(db, moderator=author)

    reasons_to_test = [
        ReportReason.SPAM,
        ReportReason.OFF_TOPIC,
        ReportReason.RUDE_OR_ABUSIVE,
        ReportReason.NEEDS_IMPROVEMENT,
        ReportReason.RIGHT_INFRINGEMENT,
        ReportReason.DUPLICATE,
        ReportReason.NEED_MODERATOR_INTERVENTION,
    ]

    for reason in reasons_to_test:
        question = _create_test_question(db, author_id=author.id, site=site)

        report_in = ReportCreate(
            question_uuid=question.uuid,
            submission_uuid=None,
            answer_uuid=None,
            article_uuid=None,
            comment_uuid=None,
            reason=reason,
            reason_comment=f"Report with reason {reason}",
        )

        report = crud.report.create_with_author(
            db, obj_in=report_in, author_id=reporter.id, check_site=_noop_check_site
        )

        assert report.reason == reason
