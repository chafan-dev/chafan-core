"""Create questions, answers, and articles for the smoke test site.

Produces a realistic mix of deep-dive questions, quick tips, and published
articles across the three columns. Questions are asked by various users;
answers come from different contributors. Articles are published in the
Engineering and Quick Tips columns.
"""
from __future__ import annotations

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.richtext import RichText
from chafan_core.utils.base import ContentVisibility, get_uuid
from chafan_core.utils.validators import StrippedNonEmptyStr


# ---------------------------------------------------------------------------
# Question definitions -- realistic titles and topics
# ---------------------------------------------------------------------------

QUESTIONS = [
    {
        "key": "question_a",
        "title": "How do you handle distributed transactions in a microservices architecture?",
        "body": "We're running a microservices setup with PostgreSQL databases per service. When a single user action needs to update data across two services, we currently use a two-phase commit, but it feels heavy. Has anyone found a better pattern? We're considering Saga patterns or outbox-based event sourcing. What's worked well for you at scale?",
        "author": "account_a",
        "column": "column_a",
    },
    {
        "key": "question_b",
        "title": "What's the best way to debug memory leaks in Python web applications?",
        "body": "Our Flask application has been running for months and slowly consuming more and more RAM. We suspect a memory leak but aren't sure where to start. We've tried memory_profiler and tracemalloc, but the results are hard to interpret. What's your go-to toolkit for tracking down Python memory issues in production?",
        "author": "account_a",
        "column": "column_b",
    },
    {
        "key": "question_c",
        "title": "Should we migrate from JWT to opaque tokens for our API auth?",
        "body": "We're building a new API and currently planning to use JWTs for authentication. However, a colleague pointed out that opaque tokens give us better revocation support. We're a small team and want to keep things simple. When does JWT start becoming problematic? Is there a rule of thumb?",
        "author": "account_b",
        "column": "column_a",
    },
    {
        "key": "question_d",
        "title": "How do you structure a monorepo for multiple frontend applications?",
        "body": "Our company has 5 different web apps that share a lot of components, hooks, and utility functions. We're considering moving to a monorepo with Turborepo. What package structure have you found works best? Should all shared packages live in packages/, or is there a better convention?",
        "author": "user_e",
        "column": "column_b",
    },
    {
        "key": "question_e",
        "title": "What's your approach to database seeding in CI/CD pipelines?",
        "body": "We want to seed our test database with realistic data on every CI run, but our current seed script takes 40 seconds and we need it faster. We're using PostgreSQL with a mix of SQL files and Python seed scripts. Any tips for speeding this up? We're also open to using test containers.",
        "author": "user_g",
        "column": "column_b",
    },
    {
        "key": "question_f",
        "title": "How to handle feature flags across a multi-region deployment?",
        "body": "We deploy to three regions and currently manage feature flags with a centralized Redis store. When we flip a flag, the propagation delay between regions is noticeable. Should we use per-region flag stores with eventual consistency, or is there a better approach?",
        "author": "user_f",
        "column": "column_a",
    },
]


# ---------------------------------------------------------------------------
# Answer definitions -- realistic replies to the questions above
# ---------------------------------------------------------------------------

ANSWERS = [
    {
        "key": "answer_a",
        "question": "question_a",
        "body": "We've been using the Saga pattern with a choreography-based approach. Each service publishes domain events that trigger the next step in the saga. For compensating transactions, we store the reverse operations alongside the forward ones. It's been working well for us at about 10k requests per second. The key insight is to make your events idempotent.",
        "author": "user_c",
    },
    {
        "key": "answer_b",
        "question": "question_a",
        "body": "We went with the outbox pattern + CDC (change data capture) using Debezium. It decouples the database transaction from the message publishing. The outbox table is written within the same transaction as your business logic, and a separate process reads from the outbox and publishes to Kafka. This gives you exactly-once semantics without 2PC.",
        "author": "user_d",
    },
    {
        "key": "answer_c",
        "question": "question_b",
        "body": "Start with `objgraph` to find the most common types in your heap between snapshots. Then use `py-spy` to get flame graphs of a running process -- it showed us that a third-party library was caching results in a global dict without limits. The fix was swapping it for `functools.cache` with a maxsize.",
        "author": "user_e",
    },
    {
        "key": "answer_d",
        "question": "question_c",
        "body": "For most APIs, JWTs are fine. The revocation problem is overblown -- use short-lived access tokens (15 min) with refresh tokens in httpOnly cookies. The refresh token is your opaque token. This gives you the best of both worlds. We switched from opaque tokens to this hybrid approach and it simplified our auth layer significantly.",
        "author": "account_a",
    },
    {
        "key": "answer_e",
        "question": "question_d",
        "body": "We use pnpm workspaces with a simple structure: `apps/` for the actual applications and `packages/` for shared libraries. Each shared package has its own package.json with a unique scoped name. The key is using a build cache (Turborepo handles this well) and keeping dependencies isolated per-package.",
        "author": "account_a",
    },
    {
        "key": "answer_f",
        "question": "question_e",
        "body": "We switched to using `pg_dump` of a pre-seeded database instead of running seed scripts. The dump is about 50MB and loads in under 2 seconds. We keep it checked in and refresh it weekly. For truly dynamic data, we use a lightweight seed script that runs in parallel using asyncio.",
        "author": "user_c",
    },
    {
        "key": "answer_g",
        "question": "question_f",
        "body": "We use LaunchDarkly and it handles multi-region flag propagation automatically. But if you want to self-host, we built something on top of etcd which gives you strong consistency across regions. The tradeoff is you need etcd clusters in each region with cross-cluster replication.",
        "author": "user_f",
    },
]


# ---------------------------------------------------------------------------
# Article definitions -- realistic long-form content
# ---------------------------------------------------------------------------

ARTICLES = [
    {
        "key": "article_a",
        "title": "Building a Real-Time Notification System with PostgreSQL Listeners",
        "body": (
            "We needed to send real-time notifications to thousands of concurrent users without "
            "the complexity of a full WebSocket infrastructure. PostgreSQL's LISTEN/NOTIFY turned "
            "out to be the perfect solution.\n\n"
            "## The Architecture\n\n"
            "Each application instance maintains a connection pool and listens on a dedicated channel "
            "per user. When an event is published, we notify the channel and the relevant listeners "
            "push the notification to the user's browser via WebSocket.\n\n"
            "## Performance Numbers\n\n"
            "On our production database (AWS r5.xlarge), we handle about 5,000 concurrent LISTEN "
            "connections with sub-50ms notification latency. The key is using connection pooling "
            "and keeping the payload small.\n\n"
            "## Lessons Learned\n\n"
            "1. Set a timeout on LISTEN to detect stale connections\n2. Use NOTIFY with payload "
            "to avoid extra lookups\n3. Monitor connection pool usage carefully\n4. Handle connection "
            "loss gracefully with exponential backoff"
        ),
        "author": "account_a",
        "column": "column_a",
    },
    {
        "key": "article_b",
        "title": "10 Python One-Liners That Save Us Hours Every Week",
        "body": (
            "Over the years, our team has collected a set of Python one-liners and small patterns "
            "that come up again and again. Here are our favorites:\n\n"
            "## 1. Counter with defaultdict\n"
            "`from collections import defaultdict; c = defaultdict(int)`\n"
            "No more checking if a key exists before incrementing.\n\n"
            "## 2. Grouping with itertools.groupby\n"
            "Sort your data first, then group. Works great for report generation.\n\n"
            "## 3. Context managers for file handling\n"
            "The `with` statement isn't just for files -- use it for any resource that needs "
            "cleaning up. Our team wrote a decorator-based context manager for database sessions "
            "that reduced connection leaks by 80%.\n\n"
            "## 4. Pathlib for file operations\n"
            "Stop using `os.path`. `pathlib.Path` is cleaner, more composable, and handles "
            "path resolution correctly across platforms.\n\n"
            "## 5. dataclasses for data containers\n"
            "Before dataclasses, we wrote dozens of `__init__`, `__repr__`, and `__eq__` methods "
            "by hand. Now we just define the fields and let the decorator do the rest.\n\n"
            "These seem small, but multiplied across hundreds of files and dozens of developers, "
            "they make a real difference in code quality and development speed."
        ),
        "author": "user_e",
        "column": "column_b",
    },
    {
        "key": "article_c",
        "title": "Our Journey from单体架构 to Microservices: A Post-Mortem",
        "body": (
            "Two years ago, we had a single monolithic Django application serving 100k daily "
            "users. Today, we run 12 microservices across Kubernetes. Here's what worked, what "
            "didn't, and what we'd do differently.\n\n"
            "## What Triggered the Split\n\n"
            "The monolith was still fast enough -- the bottleneck was our team's ability to "
            "deploy. Merges conflicted constantly, and a single database migration could block "
            "all teams for hours.\n\n"
            "## Our Split Strategy\n\n"
            "We used the strangler fig pattern: new features went into new services, and we "
            "incrementally moved functionality out of the monolith. This avoided the big bang "
            "rewrite that so many teams attempt.\n\n"
            "## The Surprising Costs\n\n"
            "1. Distributed tracing: We underestimated how much debugging cost without proper "
            "observability. OpenTelemetry was a lifesaver.\n2. Data consistency: Eventually "
            "consistent data is hard to reason about. We had to rebuild our reporting layer "
            "from scratch.\n3. Team topology: Conway's Law hit us hard. Our service boundaries "
            "had to match our team boundaries.\n\n"
            "## What We'd Do Differently\n"
            "We split too early. We should have waited until deployment frequency became the "
            "bottleneck, not the codebase size. A well-organized modular monolith with good "
            "boundaries could have served us for another year."
        ),
        "author": "account_a",
        "column": "column_a",
    },
    {
        "key": "article_d",
        "title": "CSS Container Queries: The Future of Responsive Design",
        "body": (
            "Container queries let you style elements based on their container's size, not the "
            "viewport. This is a paradigm shift for component-based design.\n\n"
            "## Why This Matters\n\n"
            "With media queries, a card component looks different at 768px regardless of whether "
            "it's in a sidebar or a main content area. Container queries fix this: the card "
            "responds to its own container.\n\n"
            "## Basic Syntax\n\n"
            "```css\n"
            ".card-container {\n"
            "  container-type: inline-size;\n"
            "}\n\n"
            "@container (min-width: 400px) {\n"
            "  .card { display: grid; grid-template-columns: 200px 1fr; }\n"
            "}\n"
            "```\n\n"
            "## Browser Support\n\n"
            "Chrome 105+, Firefox 110+, Safari 16+. For older browsers, a polyfill exists but "
            "has limitations with nested containers.\n\n"
            "This is the most significant CSS feature addition since flexbox, in our opinion."
        ),
        "author": "user_h",
        "column": "column_b",
    },
]


# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------


def _check_site(site) -> None:
    """No-op check_site callback for comment creation."""
    pass


def create_questions(db, users: dict, columns: dict, site) -> dict:
    """Create all questions. Returns a mapping from key to Question model."""
    result = {}
    for q in QUESTIONS:
        author = users[q["author"]]
        existing = (
            db.query(models.Question)
            .filter_by(site_id=site.id, title=q["title"])
            .first()
        )
        if existing:
            result[q["key"]] = existing
            continue

        question = crud.question.create_with_author(
            db,
            obj_in=schemas.QuestionCreate(
                site_uuid=site.uuid,
                title=StrippedNonEmptyStr(q["title"]),
            ),
            author_id=author.id,
        )
        result[q["key"]] = question
    db.flush()
    return result


def create_answers(db, users: dict, questions: dict) -> dict:
    """Create all answers. Returns a mapping from key to Answer model."""
    result = {}
    for a in ANSWERS:
        question = questions[a["question"]]
        author = users[a["author"]]
        existing = (
            db.query(models.Answer)
            .filter_by(question_id=question.id, author_id=author.id)
            .first()
        )
        if existing:
            result[a["key"]] = existing
            continue

        answer = crud.answer.create_with_author(
            db,
            obj_in=schemas.AnswerCreate(
                question_uuid=question.uuid,
                content=RichText(
                    source=a["body"],
                    editor="tiptap",
                    rendered_text=a["body"],
                ),
                is_published=True,
                visibility=ContentVisibility.ANYONE,
                writing_session_uuid=get_uuid(),
            ),
            author_id=author.id,
            site_id=question.site_id,
        )
        result[a["key"]] = answer
    db.flush()
    return result


def create_articles(db, users: dict, columns: dict, site) -> dict:
    """Create all articles. Returns a mapping from key to Article model."""
    result = {}
    for art in ARTICLES:
        author = users[art["author"]]
        column = columns[art["column"]]
        existing = (
            db.query(models.Article)
            .filter_by(
                article_column_id=column.id,
                title=art["title"],
            )
            .first()
        )
        if existing:
            result[art["key"]] = existing
            continue

        article = crud.article.create_with_author(
            db,
            obj_in=schemas.ArticleCreate(
                title=StrippedNonEmptyStr(art["title"]),
                content=RichText(
                    source=art["body"],
                    editor="tiptap",
                ),
                article_column_uuid=column.uuid,
                is_published=True,
                writing_session_uuid=get_uuid(),
                visibility=ContentVisibility.ANYONE,
            ),
            author_id=author.id,
        )
        result[art["key"]] = article
    db.flush()
    return result
