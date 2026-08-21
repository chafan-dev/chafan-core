"""The URL fields on /me were unwritable until these values were coerced.

Pydantic v2 parses AnyHttpUrl into a Url object; the columns behind
avatar_url, gif_avatar_url, homepage_url, linkedin_url and zhihu_url are
plain String, so the object reached psycopg2 and the write raised.
"""

from pydantic import SecretStr

from chafan_core.app.schemas.user import UserUpdateMe
from chafan_core.app.services.me import stringify_urls

URL_FIELDS = (
    "avatar_url",
    "gif_avatar_url",
    "homepage_url",
    "linkedin_url",
    "zhihu_url",
)


def _dump(**kwargs):
    return stringify_urls(UserUpdateMe(**kwargs).dict(exclude_unset=True))


def test_every_url_field_becomes_a_plain_str():
    url = "https://img.cha.fan/abc.jpg"
    data = _dump(**{field: url for field in URL_FIELDS})
    for field in URL_FIELDS:
        assert type(data[field]) is str, f"{field} is {type(data[field]).__name__}"
        assert data[field] == url


def test_url_fields_are_objects_without_the_coercion():
    # Pin the reason this helper exists: the raw dump is not a str, which is
    # exactly what psycopg2 cannot adapt to a text parameter.
    raw = UserUpdateMe(avatar_url="https://img.cha.fan/abc.jpg").dict(
        exclude_unset=True
    )
    assert not isinstance(raw["avatar_url"], str)


def test_none_is_left_alone():
    data = _dump(avatar_url=None, homepage_url=None)
    assert data["avatar_url"] is None
    assert data["homepage_url"] is None


def test_password_is_not_coerced():
    # A jsonable_encoder pass over the whole payload would turn the SecretStr
    # into its mask, and crud.user.update hashes whatever it finds here.
    data = _dump(password="hunter2hunter2")
    assert isinstance(data["password"], SecretStr)
    assert data["password"].get_secret_value() == "hunter2hunter2"


def test_plain_string_fields_are_untouched():
    data = _dump(full_name="狗管理", github_username="chai", handle="chai_inu")
    assert data["full_name"] == "狗管理"
    assert data["github_username"] == "chai"
    assert data["handle"] == "chai_inu"


def test_covers_every_url_field_the_schema_declares():
    # If a new AnyHttpUrl field is added to UserUpdateMe, it must be listed
    # above -- otherwise this suite would keep passing while that field
    # stayed unwritable.
    url = "https://example.com/x"
    populated = {}
    for name in UserUpdateMe.model_fields:
        try:
            populated[name] = UserUpdateMe(**{name: url}).dict(exclude_unset=True)[name]
        except Exception:
            continue
    from pydantic import AnyUrl

    declared = {n for n, v in populated.items() if isinstance(v, AnyUrl)}
    assert declared == set(URL_FIELDS)
