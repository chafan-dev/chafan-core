import re

from pydantic.networks import EmailStr
from pydantic.types import SecretStr

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


class CaseInsensitiveEmailStr(EmailStr):
    @classmethod
    def validate(cls, value: str) -> str:
        return EmailStr.validate(value).lower()


class StrippedNonEmptyStr(str):
    @classmethod
    def validate(cls, value: str) -> "StrippedNonEmptyStr":
        stripped = value.strip()
        assert len(stripped) > 0, "must be non-empty string"
        return StrippedNonEmptyStr(stripped)


class StrippedNonEmptyBasicStr(str):
    @classmethod
    def validate(cls, value: str) -> str:
        stripped = value.strip()
        assert len(stripped) > 0, "must be non-empty string"
        if not re.fullmatch(r"[a-zA-Z0-9-_]+", stripped):
            raise ValueError(
                "Only alphanumeric, underscore or hyphen is allowed in ID."
            )
        return stripped


_uuid_alphabet = set("23456789ABCDEFGHJKLMNPQRSTUVWXYZ" "abcdefghijkmnopqrstuvwxyz")


class UUID(str):
    @classmethod
    def validate(cls, value: str) -> str:
        assert len(value) == UUID_LENGTH, "invalid UUID length"
        assert all([c in _uuid_alphabet for c in value])
        return value
