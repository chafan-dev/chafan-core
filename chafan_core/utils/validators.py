import re

from pydantic import AfterValidator, EmailStr
from pydantic.types import SecretStr
from typing_extensions import Annotated

from chafan_core.utils.base import UUID_LENGTH, HTTPException_


def validate_password(password: SecretStr) -> SecretStr:
    if len(password.get_secret_value()) <= 2:
        raise ValueError("Password is too short.")
    if not password.get_secret_value().isascii():
        raise ValueError("Password is not ASCII.")
    return password


def validate_question_title(question_title: str) -> str:
    if len(question_title) < 5:
        raise ValueError("Question title is too short.")
    return question_title


def validate_submission_title(submission_title: str) -> str:
    if len(submission_title) < 5:
        raise ValueError("Submission title is too short.")
    return submission_title


def validate_article_title(article_title: str) -> str:
    if len(article_title) < 5:
        raise ValueError("Article title is too short.")
    return article_title


def validate_answer_body(answer_body: str) -> str:
    if len(answer_body) < 5:
        raise ValueError("Answer body is too short.")
    return answer_body


def validate_comment_body(comment_body: str) -> str:
    if len(comment_body) == 0:
        raise ValueError("Comment body can't be empty.")
    return comment_body


def validate_message_body(message_body: str) -> str:
    if len(message_body) == 0:
        raise ValueError("Message body can't be empty.")
    return message_body


def check_password(password: SecretStr) -> None:
    try:
        validate_password(password)
    except ValueError as e:
        raise HTTPException_(status_code=400, detail=e.args[0])


CaseInsensitiveEmailStr = Annotated[EmailStr, AfterValidator(lambda x: x.lower())]


def validate_StrippedNonEmptyStr(value: str) -> str:
    stripped = value.strip()
    assert len(stripped) > 0, "must be non-empty string"
    return stripped


StrippedNonEmptyStr = Annotated[str, AfterValidator(validate_StrippedNonEmptyStr)]


def validate_StrippedNonEmptyBasicStr(value: str) -> str:
    stripped = value.strip()
    assert len(stripped) > 0, "must be non-empty string"
    if not re.fullmatch(r"[a-zA-Z0-9-_]+", stripped):
        raise ValueError("Only alphanumeric, underscore or hyphen is allowed in ID.")
    return stripped


StrippedNonEmptyBasicStr = Annotated[
    str, AfterValidator(validate_StrippedNonEmptyBasicStr)
]


_uuid_alphabet = set("23456789ABCDEFGHJKLMNPQRSTUVWXYZ" "abcdefghijkmnopqrstuvwxyz")


def validate_UUID(value: str) -> str:
    assert len(value) == UUID_LENGTH, "invalid UUID length"
    assert all([c in _uuid_alphabet for c in value])
    return value


UUID = Annotated[str, validate_UUID]


# Title validators as Annotated types
ArticleTitle = Annotated[str, AfterValidator(validate_article_title)]
QuestionTitle = Annotated[str, AfterValidator(validate_question_title)]
SubmissionTitle = Annotated[str, AfterValidator(validate_submission_title)]

# Body validators as Annotated types
MessageBody = Annotated[str, AfterValidator(validate_message_body)]

# Password validator as Annotated type
ValidPassword = Annotated[SecretStr, AfterValidator(validate_password)]


# Phone number validators
def validate_country_code(v: str) -> str:
    if v.isdigit() and len(v) >= 1 and len(v) <= 3:
        return v
    raise ValueError(f"Invalid country code: {v}")


def validate_subscriber_number(v: str) -> str:
    if v.isdigit() and len(v) >= 1 and len(v) <= 12:
        return v
    raise ValueError(f"Invalid subscriber number: {v}")


CountryCode = Annotated[str, AfterValidator(validate_country_code)]
SubscriberNumber = Annotated[str, AfterValidator(validate_subscriber_number)]


# Positive integer validator
def validate_positive_int(v: int) -> int:
    if v <= 0:
        raise ValueError("Value must be positive.")
    return v


PositiveInt = Annotated[int, AfterValidator(validate_positive_int)]
