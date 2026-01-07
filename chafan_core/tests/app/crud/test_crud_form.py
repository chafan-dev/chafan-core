import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.form import (
    FormCreate,
    FormField,
    TextField,
    SingleChoiceField,
    MultipleChoicesField,
)
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


def test_create_form_with_author(db: Session) -> None:
    """Test creating a form with an author."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Test Survey",
        form_fields=[
            FormField(
                unique_name="q1",
                field_type=TextField(desc="What is your name?"),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert form.author_id == author.id
    assert form.title == "Test Survey"
    assert form.uuid is not None
    assert form.created_at is not None
    assert form.updated_at is not None


def test_create_form_with_text_field(db: Session) -> None:
    """Test creating a form with a text field."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Text Survey",
        form_fields=[
            FormField(
                unique_name="name_field",
                field_type=TextField(desc="Enter your name"),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert len(form.form_fields) == 1
    assert form.form_fields[0]["unique_name"] == "name_field"


def test_create_form_with_single_choice_field(db: Session) -> None:
    """Test creating a form with a single choice field."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Single Choice Survey",
        form_fields=[
            FormField(
                unique_name="favorite_color",
                field_type=SingleChoiceField(
                    desc="What is your favorite color?",
                    choices=["Red", "Blue", "Green"],
                ),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert len(form.form_fields) == 1


def test_create_form_with_multiple_choices_field(db: Session) -> None:
    """Test creating a form with a multiple choices field."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Multiple Choices Survey",
        form_fields=[
            FormField(
                unique_name="hobbies",
                field_type=MultipleChoicesField(
                    desc="Select your hobbies",
                    choices=["Reading", "Sports", "Music", "Gaming"],
                ),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert len(form.form_fields) == 1


def test_create_form_with_multiple_fields(db: Session) -> None:
    """Test creating a form with multiple fields of different types."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Comprehensive Survey",
        form_fields=[
            FormField(
                unique_name="name",
                field_type=TextField(desc="Your name"),
            ),
            FormField(
                unique_name="gender",
                field_type=SingleChoiceField(
                    desc="Gender",
                    choices=["Male", "Female", "Other"],
                ),
            ),
            FormField(
                unique_name="interests",
                field_type=MultipleChoicesField(
                    desc="Your interests",
                    choices=["Tech", "Art", "Science"],
                ),
            ),
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert len(form.form_fields) == 3


def test_get_form_by_id(db: Session) -> None:
    """Test getting a form by ID."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Test Form",
        form_fields=[
            FormField(
                unique_name="q1",
                field_type=TextField(desc="Question 1"),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    retrieved = crud.form.get(db, id=form.id)
    assert retrieved is not None
    assert retrieved.id == form.id


def test_get_form_by_uuid(db: Session) -> None:
    """Test getting a form by UUID."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Test Form",
        form_fields=[
            FormField(
                unique_name="q1",
                field_type=TextField(desc="Question 1"),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    retrieved = crud.form.get_by_uuid(db, uuid=form.uuid)
    assert retrieved is not None
    assert retrieved.uuid == form.uuid


def test_get_form_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent form."""
    result = crud.form.get(db, id=99999999)
    assert result is None


def test_get_form_by_uuid_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get_by_uuid returns None for non-existent UUID."""
    result = crud.form.get_by_uuid(db, uuid="nonexistent-uuid")
    assert result is None


def test_form_timestamps(db: Session) -> None:
    """Test that forms have correct timestamps."""
    author = _create_test_user(db)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    form_in = FormCreate(
        title="Timestamp Test Form",
        form_fields=[
            FormField(
                unique_name="q1",
                field_type=TextField(desc="Question"),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert form.created_at is not None
    assert form.updated_at is not None
    assert before_create <= form.created_at <= after_create
    assert before_create <= form.updated_at <= after_create


def test_multiple_forms_by_same_author(db: Session) -> None:
    """Test that an author can create multiple forms."""
    author = _create_test_user(db)

    forms = []
    for i in range(3):
        form_in = FormCreate(
            title=f"Form {i}",
            form_fields=[
                FormField(
                    unique_name=f"q_{i}",
                    field_type=TextField(desc=f"Question {i}"),
                )
            ],
        )
        form = crud.form.create_with_author(db, obj_in=form_in, author=author)
        forms.append(form)

    assert len(forms) == 3
    assert all(f.author_id == author.id for f in forms)
    # Each form should have unique UUID
    uuids = [f.uuid for f in forms]
    assert len(set(uuids)) == 3


def test_form_with_correct_answer(db: Session) -> None:
    """Test creating a form with a correct answer for quiz-style forms."""
    author = _create_test_user(db)

    form_in = FormCreate(
        title="Quiz",
        form_fields=[
            FormField(
                unique_name="capital",
                field_type=SingleChoiceField(
                    desc="What is the capital of France?",
                    choices=["London", "Paris", "Berlin"],
                    correct_choice="Paris",
                    score=10,
                ),
            )
        ],
    )

    form = crud.form.create_with_author(db, obj_in=form_in, author=author)

    assert form is not None
    assert form.title == "Quiz"
