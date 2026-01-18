import asyncio
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.site import SiteCreate, SiteUpdate
from chafan_core.app.schemas.question import QuestionCreate
from chafan_core.app.schemas.submission import SubmissionCreate
from chafan_core.app.schemas.user import UserCreate
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


def test_create_site_with_permission_type_private(db: Session) -> None:
    """Test creating a private site."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Private Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="A private test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    assert site is not None
    assert site.name == site_in.name
    assert site.subdomain == site_in.subdomain
    assert site.description == site_in.description
    assert site.moderator_id == moderator.id
    assert site.uuid is not None
    assert site.created_at is not None
    # Private site should have all public flags as False
    assert site.public_readable is False
    assert site.public_writable_question is False
    assert site.public_writable_submission is False
    assert site.public_writable_answer is False
    assert site.public_writable_comment is False


def test_create_site_with_permission_type_public(db: Session) -> None:
    """Test creating a public site."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Public Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="A public test site",
        permission_type="public",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    assert site is not None
    # Public site should have public flags as True
    assert site.public_readable is True
    assert site.public_writable_question is True
    assert site.public_writable_answer is True
    assert site.public_writable_comment is True


def test_create_site_with_category_topic(db: Session) -> None:
    """Test creating a site with a category topic."""
    moderator = _create_test_user(db)

    # Create a category topic
    from chafan_core.app.schemas.topic import TopicCreate

    topic_in = TopicCreate(name=f"Category {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)
    crud.topic.update(db, db_obj=topic, obj_in={"is_category": True})

    site_in = SiteCreate(
        name=f"Categorized Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="A site with category",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=topic.id
    )

    assert site is not None
    assert site.category_topic_id == topic.id


def test_get_site_by_subdomain(db: Session) -> None:
    """Test retrieving a site by subdomain."""
    moderator = _create_test_user(db)
    subdomain = random_short_lower_string()

    site_in = SiteCreate(
        name=f"Site for subdomain lookup {random_short_lower_string()}",
        subdomain=subdomain,
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    retrieved_site = crud.site.get_by_subdomain(db, subdomain=subdomain)
    assert retrieved_site is not None
    assert retrieved_site.id == site.id
    assert retrieved_site.subdomain == subdomain


def test_get_site_by_id(db: Session) -> None:
    """Test retrieving a site by ID."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Site for ID lookup {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    retrieved_site = crud.site.get_by_id(db, id=site.id)
    assert retrieved_site is not None
    assert retrieved_site.id == site.id


def test_get_site_by_name(db: Session) -> None:
    """Test retrieving a site by name."""
    moderator = _create_test_user(db)
    name = f"Unique Site Name {random_short_lower_string()}"

    site_in = SiteCreate(
        name=name,
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    retrieved_site = crud.site.get_by_name(db, name=name)
    assert retrieved_site is not None
    assert retrieved_site.id == site.id
    assert retrieved_site.name == name


def test_get_site_by_uuid(db: Session) -> None:
    """Test retrieving a site by UUID."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Site for UUID lookup {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    retrieved_site = crud.site.get_by_uuid(db, uuid=site.uuid)
    assert retrieved_site is not None
    assert retrieved_site.id == site.id
    assert retrieved_site.uuid == site.uuid


def test_get_all_sites(db: Session) -> None:
    """Test getting all sites."""
    initial_count = len(crud.site.get_all(db))

    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Site for get_all {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    all_sites = crud.site.get_all(db)
    assert len(all_sites) == initial_count + 1


def test_get_all_public_readable(db: Session) -> None:
    """Test getting all public readable sites."""
    moderator = _create_test_user(db)

    # Create a public site
    public_site_in = SiteCreate(
        name=f"Public Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Public site",
        permission_type="public",
    )

    public_site = crud.site.create_with_permission_type(
        db, obj_in=public_site_in, moderator=moderator, category_topic_id=None
    )

    # Create a private site
    private_site_in = SiteCreate(
        name=f"Private Site {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Private site",
        permission_type="private",
    )

    private_site = crud.site.create_with_permission_type(
        db, obj_in=private_site_in, moderator=moderator, category_topic_id=None
    )

    public_readable_sites = crud.site.get_all_public_readable(db)
    public_ids = [s.id for s in public_readable_sites]

    assert public_site.id in public_ids
    assert private_site.id not in public_ids


def test_get_multi_questions(db: Session) -> None:
    """Test getting paginated questions for a site."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Site for questions {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    # Create some questions for the site
    for i in range(5):
        question_in = QuestionCreate(
            site_uuid=site.uuid,
            title=f"Question {i} {random_short_lower_string()}",
        )
        crud.question.create_with_author(db, obj_in=question_in, author_id=moderator.id)

    # Test pagination
    questions_page1 = crud.site.get_multi_questions(db, db_obj=site, skip=0, limit=2)
    assert len(questions_page1) == 2

    questions_page2 = crud.site.get_multi_questions(db, db_obj=site, skip=2, limit=2)
    assert len(questions_page2) == 2

    questions_all = crud.site.get_multi_questions(db, db_obj=site, skip=0, limit=10)
    assert len(questions_all) == 5


def test_get_multi_submissions(db: Session) -> None:
    """Test getting paginated submissions for a site."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Site for submissions {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    # Create some submissions for the site
    for i in range(5):
        submission_in = SubmissionCreate(
            site_uuid=site.uuid,
            title=f"Submission {i} {random_short_lower_string()}",
            url=f"https://example.com/submission-{i}",
        )
        crud.submission.create_with_author(
            db, obj_in=submission_in, author_id=moderator.id
        )

    # Test pagination
    submissions_page1 = crud.site.get_multi_submissions(
        db, db_obj=site, skip=0, limit=2
    )
    assert len(submissions_page1) == 2

    submissions_page2 = crud.site.get_multi_submissions(
        db, db_obj=site, skip=2, limit=2
    )
    assert len(submissions_page2) == 2

    submissions_all = crud.site.get_multi_submissions(db, db_obj=site, skip=0, limit=10)
    assert len(submissions_all) == 5


def test_get_all_with_category_topic_ids(db: Session) -> None:
    """Test getting sites by category topic ID."""
    moderator = _create_test_user(db)

    # Create a category topic
    from chafan_core.app.schemas.topic import TopicCreate

    topic_in = TopicCreate(name=f"Category {random_short_lower_string()}")
    topic = crud.topic.create(db, obj_in=topic_in)
    crud.topic.update(db, db_obj=topic, obj_in={"is_category": True})

    # Create a site with this category
    site_in = SiteCreate(
        name=f"Site with category {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site with category",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=topic.id
    )

    # Create a site without this category
    other_site_in = SiteCreate(
        name=f"Site without category {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Test site without category",
        permission_type="private",
    )

    other_site = crud.site.create_with_permission_type(
        db, obj_in=other_site_in, moderator=moderator, category_topic_id=None
    )

    sites_with_category = crud.site.get_all_with_category_topic_ids(
        db, category_topic_id=topic.id
    )
    site_ids = [s.id for s in sites_with_category]

    assert site.id in site_ids
    assert other_site.id not in site_ids


def test_update_site(db: Session) -> None:
    """Test updating a site."""
    moderator = _create_test_user(db)

    site_in = SiteCreate(
        name=f"Original Name {random_short_lower_string()}",
        subdomain=random_short_lower_string(),
        description="Original description",
        permission_type="private",
    )

    site = crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )

    new_description = "Updated description"
    crud.site.update(db, db_obj=site, obj_in={"description": new_description})

    db.refresh(site)
    assert site.description == new_description


def test_get_site_returns_none_for_nonexistent_subdomain(db: Session) -> None:
    """Test that get_by_subdomain returns None for non-existent subdomain."""
    result = crud.site.get_by_subdomain(db, subdomain="nonexistent-subdomain")
    assert result is None


def test_get_site_returns_none_for_nonexistent_name(db: Session) -> None:
    """Test that get_by_name returns None for non-existent name."""
    result = crud.site.get_by_name(db, name="Nonexistent Site Name")
    assert result is None


def test_get_site_returns_none_for_nonexistent_id(db: Session) -> None:
    """Test that get_by_id returns None for non-existent ID."""
    result = crud.site.get_by_id(db, id=99999999)
    assert result is None
