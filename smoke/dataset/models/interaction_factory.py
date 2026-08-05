"""Create comments, upvotes, and followers for the smoke test site.

Produces a realistic graph of interactions: users follow each other, upvote
content they find useful, and comment on questions and articles.
"""

from __future__ import annotations

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.richtext import RichText

# ---------------------------------------------------------------------------
# Follow graph -- who follows whom
# ---------------------------------------------------------------------------

FOLLOWS = [
    ("account_b", "account_a"),
    ("user_c", "account_a"),
    ("user_d", "account_a"),
    ("user_d", "account_b"),
    ("user_e", "account_a"),
    ("user_e", "user_c"),
    ("user_f", "account_a"),
    ("user_f", "user_g"),
    ("user_g", "account_b"),
    ("user_g", "user_c"),
    ("user_h", "account_a"),
    ("user_h", "user_e"),
]


# ---------------------------------------------------------------------------
# Upvote definitions -- realistic patterns across content types
# ---------------------------------------------------------------------------

QUESTION_UPVOTES = [
    ("question_a", "account_b"),
    ("question_a", "user_c"),
    ("question_a", "user_d"),
    ("question_b", "user_e"),
    ("question_b", "user_g"),
    ("question_c", "account_a"),
    ("question_c", "user_f"),
    ("question_d", "account_a"),
    ("question_e", "user_c"),
    ("question_f", "account_a"),
    ("question_f", "user_d"),
]

ANSWER_UPVOTES = [
    ("answer_a", "account_a"),
    ("answer_a", "user_d"),
    ("answer_a", "user_f"),
    ("answer_b", "account_a"),
    ("answer_b", "user_c"),
    ("answer_c", "account_b"),
    ("answer_c", "user_g"),
    ("answer_d", "account_b"),
    ("answer_d", "user_e"),
    ("answer_e", "user_e"),
    ("answer_f", "user_g"),
    ("answer_g", "account_a"),
]

ARTICLE_UPVOTES = [
    ("article_a", "user_c"),
    ("article_a", "user_d"),
    ("article_a", "user_f"),
    ("article_b", "account_a"),
    ("article_b", "user_d"),
    ("article_b", "user_h"),
    ("article_c", "account_b"),
    ("article_c", "user_e"),
    ("article_d", "account_a"),
    ("article_d", "user_e"),
]


# ---------------------------------------------------------------------------
# Comment definitions -- realistic comments on questions and articles
# ---------------------------------------------------------------------------

COMMENTS = [
    # Comments on questions
    {
        "key": "comment_a",
        "question": "question_a",
        "body": "Great question! We had a similar challenge. One thing we found helpful was adding a saga orchestrator service that coordinates the saga steps. It centralizes the state machine logic.",
        "author": "user_d",
    },
    {
        "key": "comment_b",
        "question": "question_a",
        "body": "We use the choreography approach too but with a central event bus (RabbitMQ). The key is making sure your events have a consistent schema across services. We use Protobuf for that.",
        "author": "user_f",
    },
    {
        "key": "comment_c",
        "question": "question_b",
        "body": "Don't forget about `tracemalloc`'s ability to take snapshots and compare them. You can call `tracemalloc.take_snapshot()` at two points and then use `stats.compare_to()` to see what changed.",
        "author": "user_g",
    },
    {
        "key": "comment_d",
        "question": "question_c",
        "body": "15-minute JWTs with rotating refresh tokens is basically the industry standard now. Even OAuth 2.0 spec recommends short-lived access tokens.",
        "author": "user_c",
    },
    {
        "key": "comment_e",
        "question": "question_d",
        "body": "We've been doing monorepo with Turborepo for 2 years now. The biggest win is shared CI -- one pipeline builds all apps and packages together, so you catch cross-package issues early.",
        "author": "account_a",
    },
    # Comments on articles
    {
        "key": "comment_f",
        "article": "article_a",
        "body": "We use a similar approach but with PostgreSQL logical replication to distribute notifications to regional services. Cuts down latency for multi-region deployments.",
        "author": "user_f",
    },
    {
        "key": "comment_g",
        "article": "article_a",
        "body": "What connection pool size do you use per instance? We're at 50 connections and starting to see contention during peak traffic.",
        "author": "user_e",
    },
    {
        "key": "comment_h",
        "article": "article_b",
        "body": "The pathlib tip is gold. We migrated our entire file I/O layer from `os.path` and found about 20 places where paths were incorrectly joined with string concatenation.",
        "author": "account_a",
    },
    {
        "key": "comment_i",
        "article": "article_c",
        "body": "'We split too early' -- this resonates. Our team is making the same mistake. The monolith is perfectly manageable with good module boundaries and a strong API layer.",
        "author": "user_c",
    },
    {
        "key": "comment_j",
        "article": "article_d",
        "body": "Container queries have been a game-changer for our component library. We can now build truly reusable components that adapt to any context without parent-specific CSS.",
        "author": "user_h",
    },
]


# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------


def _check_site(site) -> None:
    """No-op check_site callback for comment creation."""
    pass


def build_follows(db, users: dict) -> None:
    """Create the follow graph."""
    for target_key, follower_key in FOLLOWS:
        target = users[target_key]
        follower = users[follower_key]
        if follower not in target.followers:
            crud.user.add_follower(db, db_obj=target, follower=follower)
    db.flush()


def upvote_questions(db, users: dict, questions: dict) -> None:
    """Upvote questions. Returns upvoted question keys."""
    for question_key, voter_key in QUESTION_UPVOTES:
        question = questions[question_key]
        voter = users[voter_key]
        crud.question.upvote(db, db_obj=question, voter=voter)
    db.flush()


def upvote_answers(db, users: dict, answers: dict) -> None:
    """Upvote answers. Returns upvoted answer keys."""
    for answer_key, voter_key in ANSWER_UPVOTES:
        answer = answers[answer_key]
        voter = users[voter_key]
        crud.answer.upvote(db, db_obj=answer, voter=voter)
    db.flush()


def upvote_articles(db, users: dict, articles: dict) -> None:
    """Upvote articles. Returns upvoted article keys."""
    for article_key, voter_key in ARTICLE_UPVOTES:
        article = articles[article_key]
        voter = users[voter_key]
        crud.article.upvote(db, db_obj=article, voter=voter)
    db.flush()


def create_comments(db, users: dict, questions: dict, articles: dict) -> None:
    """Create all comments. Idempotent: skips a (parent, author, body) already present."""
    for c in COMMENTS:
        author = users[c["author"]]
        if "question" in c:
            parent = questions[c["question"]]
            existing = (
                db.query(models.Comment)
                .filter_by(question_id=parent.id, author_id=author.id, body=c["body"])
                .first()
            )
            if existing:
                continue
            comment_in = schemas.CommentCreate(
                content=RichText(
                    source=c["body"],
                    editor="tiptap",
                    rendered_text=c["body"],
                ),
                question_uuid=parent.uuid,
                shared_to_timeline=False,
            )
            crud.comment.create_with_author(
                db,
                obj_in=comment_in,
                author_id=author.id,
                check_site=_check_site,
            )
        elif "article" in c:
            parent = articles[c["article"]]
            existing = (
                db.query(models.Comment)
                .filter_by(article_id=parent.id, author_id=author.id, body=c["body"])
                .first()
            )
            if existing:
                continue
            comment_in = schemas.CommentCreate(
                content=RichText(
                    source=c["body"],
                    editor="tiptap",
                    rendered_text=c["body"],
                ),
                article_uuid=parent.uuid,
                shared_to_timeline=False,
            )
            crud.comment.create_with_author(
                db,
                obj_in=comment_in,
                author_id=author.id,
                check_site=_check_site,
            )
    db.flush()
