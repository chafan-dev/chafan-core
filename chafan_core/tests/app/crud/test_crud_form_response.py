import asyncio
import datetime
from sqlalchemy.orm import Session

from chafan_core.app import crud
from chafan_core.app.schemas.form import FormCreate, FormField, TextField, SingleChoiceField
from chafan_core.app.schemas.form_response import (
    FormResponseCreate,
    FormResponseField,
    TextResponseField,
    SingleChoiceResponseField,
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


def _create_test_form(db: Session, author):
    """Helper to create a test form."""
    form_in = FormCreate(
        title="Test Form",
        form_fields=[
            FormField(
                unique_name="name",
                field_type=TextField(desc="What is your name?"),
            ),
            FormField(
                unique_name="color",
                field_type=SingleChoiceField(
                    desc="Favorite color?",
                    choices=["Red", "Blue", "Green"],
                ),
            ),
        ],
    )
    return crud.form.create_with_author(db, obj_in=form_in, author=author)


def test_create_form_response_with_author(db: Session) -> None:
    """Test creating a form response with an author."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    response_in = FormResponseCreate(
        form_uuid=form.uuid,
        response_fields=[
            FormResponseField(
                unique_name="name",
                field_content=TextResponseField(desc="What is your name?", text="John"),
            ),
            FormResponseField(
                unique_name="color",
                field_content=SingleChoiceResponseField(
                    desc="Favorite color?", selected_choice="Blue"
                ),
            ),
        ],
    )

    response = crud.form_response.create_with_author(
        db, obj_in=response_in, response_author_id=response_author.id, form=form
    )

    assert response is not None
    assert response.response_author_id == response_author.id
    assert response.form_id == form.id
    assert response.created_at is not None


def test_create_form_response_with_text_field(db: Session) -> None:
    """Test creating a form response with a text field response."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    response_in = FormResponseCreate(
        form_uuid=form.uuid,
        response_fields=[
            FormResponseField(
                unique_name="name",
                field_content=TextResponseField(
                    desc="What is your name?", text="Alice Smith"
                ),
            ),
        ],
    )

    response = crud.form_response.create_with_author(
        db, obj_in=response_in, response_author_id=response_author.id, form=form
    )

    assert response is not None
    assert len(response.response_fields) >= 1


def test_create_form_response_with_single_choice(db: Session) -> None:
    """Test creating a form response with a single choice field response."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    response_in = FormResponseCreate(
        form_uuid=form.uuid,
        response_fields=[
            FormResponseField(
                unique_name="color",
                field_content=SingleChoiceResponseField(
                    desc="Favorite color?", selected_choice="Green"
                ),
            ),
        ],
    )

    response = crud.form_response.create_with_author(
        db, obj_in=response_in, response_author_id=response_author.id, form=form
    )

    assert response is not None


def test_get_form_response_by_id(db: Session) -> None:
    """Test getting a form response by ID."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    response_in = FormResponseCreate(
        form_uuid=form.uuid,
        response_fields=[
            FormResponseField(
                unique_name="name",
                field_content=TextResponseField(desc="Name?", text="Test"),
            ),
        ],
    )

    response = crud.form_response.create_with_author(
        db, obj_in=response_in, response_author_id=response_author.id, form=form
    )

    retrieved = crud.form_response.get(db, id=response.id)
    assert retrieved is not None
    assert retrieved.id == response.id


def test_get_form_response_returns_none_for_nonexistent(db: Session) -> None:
    """Test that get returns None for non-existent form response."""
    result = crud.form_response.get(db, id=99999999)
    assert result is None


def test_form_response_timestamps(db: Session) -> None:
    """Test that form responses have correct timestamps."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    before_create = datetime.datetime.now(tz=datetime.timezone.utc)

    response_in = FormResponseCreate(
        form_uuid=form.uuid,
        response_fields=[
            FormResponseField(
                unique_name="name",
                field_content=TextResponseField(desc="Name?", text="Test"),
            ),
        ],
    )

    response = crud.form_response.create_with_author(
        db, obj_in=response_in, response_author_id=response_author.id, form=form
    )

    after_create = datetime.datetime.now(tz=datetime.timezone.utc)

    assert response.created_at is not None
    assert before_create <= response.created_at <= after_create


def test_multiple_responses_to_same_form(db: Session) -> None:
    """Test that multiple users can respond to the same form."""
    form_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    responses = []
    for _ in range(3):
        response_author = _create_test_user(db)
        response_in = FormResponseCreate(
            form_uuid=form.uuid,
            response_fields=[
                FormResponseField(
                    unique_name="name",
                    field_content=TextResponseField(desc="Name?", text="Respondent"),
                ),
            ],
        )
        response = crud.form_response.create_with_author(
            db, obj_in=response_in, response_author_id=response_author.id, form=form
        )
        responses.append(response)

    assert len(responses) == 3
    assert all(r.form_id == form.id for r in responses)


def test_same_user_multiple_responses(db: Session) -> None:
    """Test that a user can submit multiple responses to a form."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)
    form = _create_test_form(db, author=form_author)

    responses = []
    for i in range(2):
        response_in = FormResponseCreate(
            form_uuid=form.uuid,
            response_fields=[
                FormResponseField(
                    unique_name="name",
                    field_content=TextResponseField(desc="Name?", text=f"Response {i}"),
                ),
            ],
        )
        response = crud.form_response.create_with_author(
            db, obj_in=response_in, response_author_id=response_author.id, form=form
        )
        responses.append(response)

    assert len(responses) == 2
    assert all(r.response_author_id == response_author.id for r in responses)


def test_response_to_different_forms(db: Session) -> None:
    """Test that a user can respond to different forms."""
    form_author = _create_test_user(db)
    response_author = _create_test_user(db)

    form1 = _create_test_form(db, author=form_author)
    form2 = _create_test_form(db, author=form_author)

    for form in [form1, form2]:
        response_in = FormResponseCreate(
            form_uuid=form.uuid,
            response_fields=[
                FormResponseField(
                    unique_name="name",
                    field_content=TextResponseField(desc="Name?", text="Test"),
                ),
            ],
        )
        response = crud.form_response.create_with_author(
            db, obj_in=response_in, response_author_id=response_author.id, form=form
        )
        assert response is not None
        assert response.form_id == form.id
