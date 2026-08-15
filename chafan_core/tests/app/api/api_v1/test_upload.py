import datetime
import hashlib
import io
import random
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from chafan_core.app import crud, image_sanitize, karma, models, object_storage, rules
from chafan_core.app.common import get_redis_cli
from chafan_core.app.config import settings
from chafan_core.app.infra.request_context import RequestContext
from chafan_core.app.services import uploads as uploads_service
from chafan_core.tests.utils.user import authentication_token_from_email
from chafan_core.tests.utils.utils import random_email
from chafan_core.utils.base import get_uuid

UPLOAD_BASE = "https://uploads.cha.fan"


def _random_rgb():
    return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def _png(rgb=None) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), rgb or _random_rgb()).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(rgb=None, description=None, gps=False) -> bytes:
    img = Image.new("RGB", (20, 20), rgb or _random_rgb())
    exif = Image.Exif()
    if description is not None:
        exif[0x010E] = description  # ImageDescription
    if gps:
        gps_ifd = exif.get_ifd(0x8825)
        gps_ifd[1] = "N"
        gps_ifd[2] = (38.0, 53.0, 0.0)
        gps_ifd[3] = "W"
        gps_ifd[4] = (77.0, 2.0, 0.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


def _gif() -> bytes:
    f1 = Image.new("RGB", (10, 10), _random_rgb())
    f2 = Image.new("RGB", (10, 10), _random_rgb())
    buf = io.BytesIO()
    f1.save(buf, format="GIF", save_all=True, append_images=[f2], loop=0, duration=100)
    return buf.getvalue()


def _set_karma(db: Session, user_id: int, value: int) -> None:
    db.expire_all()
    user = crud.user.get(db, id=user_id)
    assert user is not None
    karma.set_karma(db, user, value)
    db.commit()


def _set_coins(db: Session, user_id: int, value: int) -> None:
    db.expire_all()
    user = crud.user.get(db, id=user_id)
    assert user is not None
    crud.user.update(db, db_obj=user, obj_in={"remaining_coins": value})
    db.commit()


def _upload(client, headers, data, filename="a.png", content_type="image/png", purpose="figure"):
    return client.post(
        f"{settings.API_V1_STR}/upload/images/",
        headers=headers,
        files={"file": (filename, data, content_type)},
        data={"purpose": purpose},
    )


@pytest.fixture(autouse=True)
def configure_uploads(monkeypatch):
    monkeypatch.setattr(settings, "UPLOADS_S3_ENDPOINT_URL", "http://localhost:9000")
    monkeypatch.setattr(settings, "UPLOADS_S3_ACCESS_KEY_ID", "minioadmin")
    monkeypatch.setattr(settings, "UPLOADS_S3_SECRET_ACCESS_KEY", "minioadmin")
    monkeypatch.setattr(settings, "UPLOADS_S3_BUCKET", "test-bucket")
    monkeypatch.setattr(settings, "UPLOADS_S3_REGION", "us-east-1")
    monkeypatch.setattr(settings, "UPLOADS_PUBLIC_URL_BASE", UPLOAD_BASE)


@pytest.fixture(autouse=True)
def clear_upload_rate_limit():
    # The endpoint is rate-limited to 20/hour. Redis outlives a pytest run, so
    # a developer re-running the suite (or several modules hitting the same
    # endpoint) would otherwise trip the limiter and see spurious 429s.
    redis = get_redis_cli()
    for key in redis.scan_iter("*upload/images*"):
        redis.delete(key)
    yield


@pytest.fixture(autouse=True)
def fake_put_image(monkeypatch):
    calls = []

    def put_image(*, sha, content_type, data):
        calls.append({"sha": sha, "content_type": content_type, "data": data})

    monkeypatch.setattr(object_storage, "put_image", put_image)
    return calls


@pytest.fixture(scope="module")
def uploader(client, db):
    email = random_email()
    headers = authentication_token_from_email(client=client, email=email, db=db)
    user = crud.user.get_by_email(db, email=email)
    assert user is not None
    return {"headers": headers, "id": user.id}


def test_upload_png_success(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    data = _png()

    r = _upload(client, uploader["headers"], data, purpose="figure")
    assert r.status_code == 200, r.json()

    clean, content_type = image_sanitize.sanitize(data)
    sha = hashlib.sha256(clean).hexdigest()
    assert r.json()["url"] == f"{UPLOAD_BASE}/{sha}.png"
    assert len(fake_put_image) == 1
    assert fake_put_image[0]["sha"] == sha
    assert fake_put_image[0]["content_type"] == content_type

    db.expire_all()
    assert db.query(models.Upload).filter_by(uploader_id=uploader["id"]).count() == 1
    user = crud.user.get(db, id=uploader["id"])
    assert user.remaining_coins == 98


def test_upload_same_bytes_free(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    data = _png(_random_rgb())

    r1 = _upload(client, uploader["headers"], data, purpose="figure")
    assert r1.status_code == 200, r1.json()
    r2 = _upload(client, uploader["headers"], data, purpose="figure")
    assert r2.status_code == 200, r2.json()

    assert r1.json()["url"] == r2.json()["url"]
    assert len(fake_put_image) == 1, "the same bytes must be stored only once"

    db.expire_all()
    sha = fake_put_image[0]["sha"]
    assert db.query(models.Upload).filter_by(uploader_id=uploader["id"], sha256=sha).count() == 2
    user = crud.user.get(db, id=uploader["id"])
    assert user.remaining_coins == 98, "a re-upload of the same bytes is free"


def test_jpeg_exif_stripped(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    data = _jpeg(description="GPS location of my house", gps=True)
    assert Image.open(io.BytesIO(data)).getexif(), "fixture must carry EXIF"

    r = _upload(client, uploader["headers"], data, filename="photo.jpg", content_type="image/jpeg", purpose="figure")
    assert r.status_code == 200, r.json()

    stored = fake_put_image[0]["data"]
    assert Image.open(io.BytesIO(stored)).getexif() == {}, "stored bytes must carry no EXIF"
    assert fake_put_image[0]["sha"] == hashlib.sha256(stored).hexdigest(), (
        "the sha must be the hash of the sanitized bytes, not the raw upload"
    )


def test_same_photo_different_exif_dedupes(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    color = _random_rgb()
    a = _jpeg(rgb=color, description="first copy")
    b = _jpeg(rgb=color, description="second copy")

    r1 = _upload(client, uploader["headers"], a, filename="a.jpg", content_type="image/jpeg", purpose="figure")
    assert r1.status_code == 200, r1.json()
    r2 = _upload(client, uploader["headers"], b, filename="b.jpg", content_type="image/jpeg", purpose="figure")
    assert r2.status_code == 200, r2.json()

    assert r1.json()["url"] == r2.json()["url"], "same pixels must dedupe to one object"
    assert len(fake_put_image) == 1

    db.expire_all()
    user = crud.user.get(db, id=uploader["id"])
    assert user.remaining_coins == 98, "the second copy is free"


def test_animated_gif_stays_animated(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    data = _gif()

    r = _upload(client, uploader["headers"], data, filename="a.gif", content_type="image/gif", purpose="figure")
    assert r.status_code == 200, r.json()

    stored = fake_put_image[0]["data"]
    assert Image.open(io.BytesIO(stored)).n_frames > 1, "animated GIF must stay animated"


def test_figure_requires_karma(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 99)
    _set_coins(db, uploader["id"], 100)
    data = _png(_random_rgb())

    r = _upload(client, uploader["headers"], data, purpose="figure")
    assert r.status_code == 403, r.json()

    r = _upload(client, uploader["headers"], data, purpose="avatar")
    assert r.status_code == 200, r.json()


def test_unknown_purpose_rejected(client, db, uploader, fake_put_image):
    # `purpose` is a closed set. A third value would be neither gated by karma
    # (which tests for "figure") nor visible to the read-time misuse detection
    # (which tests for "avatar"), so it must be refused outright -- karma 0
    # here, to show the gate is not simply being sidestepped.
    _set_karma(db, uploader["id"], 0)
    _set_coins(db, uploader["id"], 100)
    data = _png(_random_rgb())

    r = _upload(client, uploader["headers"], data, purpose="banana")
    assert r.status_code == 422, r.json()
    assert fake_put_image == []

    clean, _ = image_sanitize.sanitize(data)
    sha = hashlib.sha256(clean).hexdigest()
    db.expire_all()
    assert db.query(models.Upload).filter_by(sha256=sha).count() == 0


@pytest.mark.parametrize(
    "unset",
    ["UPLOADS_S3_ENDPOINT_URL", "UPLOADS_S3_BUCKET", "UPLOADS_PUBLIC_URL_BASE"],
)
def test_incomplete_configuration_returns_503(
    client, db, uploader, fake_put_image, monkeypatch, unset
):
    # Any one of the three missing is a 503, checked before anything is stored:
    # the bucket is a NOT NULL column and the public base builds the response,
    # so a later failure would leave bytes in the store with no row.
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    monkeypatch.setattr(settings, unset, None)

    r = _upload(client, uploader["headers"], _png(_random_rgb()), purpose="figure")
    assert r.status_code == 503, r.json()
    assert fake_put_image == []


def test_zero_coins(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 0)
    data = _png(_random_rgb())

    r = _upload(client, uploader["headers"], data, purpose="figure")
    assert r.status_code == 400, r.json()

    _set_coins(db, uploader["id"], 100)
    assert _upload(client, uploader["headers"], data, purpose="figure").status_code == 200

    _set_coins(db, uploader["id"], 0)
    r = _upload(client, uploader["headers"], data, purpose="figure")
    assert r.status_code == 200, "re-uploading already-stored bytes must not charge coins"

    db.expire_all()
    user = crud.user.get(db, id=uploader["id"])
    assert user.remaining_coins == 0


def test_text_file_rejected(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)

    r = _upload(client, uploader["headers"], b"not an image", filename="fake.png", content_type="image/png", purpose="figure")
    assert r.status_code == 415, r.json()
    assert fake_put_image == []


def test_oversized_file_rejected(client, db, uploader):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)
    data = b"\x00" * (5_000_000 + 1)

    r = _upload(client, uploader["headers"], data, filename="big.png", content_type="image/png", purpose="figure")
    assert r.status_code in (413, 422), r.json()


def test_upload_requires_auth(client, db, uploader):
    r = client.post(
        f"{settings.API_V1_STR}/upload/images/",
        files={"file": ("a.png", _png(), "image/png")},
        data={"purpose": "figure"},
    )
    assert r.status_code in (401, 403), r.json()


def test_vditor_endpoint_removed(client):
    r = client.post(f"{settings.API_V1_STR}/upload/vditor/")
    assert r.status_code == 404


def test_find_usages_and_orphans(db, uploader):
    sha = hashlib.sha256(_png()).hexdigest()
    crud.upload.create(
        db,
        uploader_id=uploader["id"],
        sha256=sha,
        content_type="image/png",
        size_bytes=10,
        purpose="figure",
        storage_bucket="test-bucket",
    )
    db.commit()

    assert uploads_service.find_usages(db, sha=sha) == []
    assert any(u.sha256 == sha for u in uploads_service.find_orphans(db))

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    comment = models.Comment(
        uuid=get_uuid(),
        author_id=uploader["id"],
        body=f"<img src='https://uploads.cha.fan/{sha}.png'>",
        body_text="an image",
        created_at=now,
        updated_at=now,
    )
    db.add(comment)
    db.commit()

    assert uploads_service.find_usages(db, sha=sha) == [f"comment:{comment.id}"]
    assert not any(u.sha256 == sha for u in uploads_service.find_orphans(db))


def test_find_usages_covers_avatars(db, uploader):
    # An avatar is never embedded in a body: it lives on the user row. Without
    # those two columns every avatar ever uploaded reads as an orphan.
    sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    gif_sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    crud.upload.create(
        db,
        uploader_id=uploader["id"],
        sha256=sha,
        content_type="image/png",
        size_bytes=10,
        purpose="avatar",
        storage_bucket="test-bucket",
    )
    db.commit()
    assert uploads_service.find_usages(db, sha=sha) == []

    user = crud.user.get(db, id=uploader["id"])
    crud.user.update(
        db,
        db_obj=user,
        obj_in={
            "avatar_url": f"{UPLOAD_BASE}/{sha}.png",
            "gif_avatar_url": f"{UPLOAD_BASE}/{gif_sha}.gif",
        },
    )
    db.commit()

    assert uploads_service.find_usages(db, sha=sha) == [f"user_avatar:{user.id}"]
    assert uploads_service.find_usages(db, sha=gif_sha) == [
        f"user_gif_avatar:{user.id}"
    ]
    assert not any(u.sha256 == sha for u in uploads_service.find_orphans(db))


def test_find_usages_covers_question_description(
    db, uploader, normal_user_authored_question_uuid
):
    sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    crud.upload.create(
        db,
        uploader_id=uploader["id"],
        sha256=sha,
        content_type="image/png",
        size_bytes=10,
        purpose="figure",
        storage_bucket="test-bucket",
    )
    db.commit()
    assert uploads_service.find_usages(db, sha=sha) == []

    question = crud.question.get_by_uuid(db, uuid=normal_user_authored_question_uuid)
    assert question is not None
    question.description = f"<img src='{UPLOAD_BASE}/{sha}.png'>"
    db.add(question)
    db.commit()

    assert uploads_service.find_usages(db, sha=sha) == [f"question:{question.id}"]
    assert not any(u.sha256 == sha for u in uploads_service.find_orphans(db))


def _create_upload(db, uploader_id, sha, purpose):
    crud.upload.create(
        db,
        uploader_id=uploader_id,
        sha256=sha,
        content_type="image/png",
        size_bytes=10,
        purpose=purpose,
        storage_bucket="test-bucket",
    )
    db.commit()


def test_misdeclared_avatars_logic(db, uploader):
    avatar_sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    figure_sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    both_sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    never_sha = hashlib.sha256(_png(_random_rgb())).hexdigest()

    _create_upload(db, uploader["id"], avatar_sha, "avatar")
    _create_upload(db, uploader["id"], figure_sha, "figure")
    _create_upload(db, uploader["id"], both_sha, "avatar")
    _create_upload(db, uploader["id"], both_sha, "figure")

    body = (
        f"<img src='https://uploads.cha.fan/{avatar_sha}.png'>"
        f"<img src='https://uploads.cha.fan/{figure_sha}.png'>"
        f"<img src='https://uploads.cha.fan/{both_sha}.png'>"
        f"<img src='https://uploads.cha.fan/{never_sha}.png'>"
    )
    ctx = RequestContext(principal_id=uploader["id"])
    try:
        result = uploads_service.misdeclared_avatars(
            ctx, author_id=uploader["id"], body=body
        )
    finally:
        ctx.close()
    assert result == [avatar_sha]


def test_misdeclared_avatar_reported_once(db, uploader, monkeypatch):
    sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    _create_upload(db, uploader["id"], sha, "avatar")

    reports = []
    monkeypatch.setattr(uploads_service, "report_msg", reports.append)

    article = SimpleNamespace(
        id=random.randint(10**6, 10**7),
        uuid="fake-article-uuid",
        author_id=uploader["id"],
        body=f"<img src='https://uploads.cha.fan/{sha}.png'>",
    )
    ctx = RequestContext(principal_id=uploader["id"])
    try:
        uploads_service.check_article_for_misdeclared_avatars(ctx, article=article)
        uploads_service.check_article_for_misdeclared_avatars(ctx, article=article)
    finally:
        ctx.close()

    assert len(reports) == 1
    assert sha in reports[0]


def test_misdeclared_avatar_swallowed_on_failure(db, uploader, monkeypatch):
    def boom(ctx, *, author_id, body):
        raise RuntimeError("upload table down")

    monkeypatch.setattr(uploads_service, "misdeclared_avatars", boom)
    article = SimpleNamespace(id=1, uuid="x", author_id=uploader["id"], body="x")
    ctx = RequestContext(principal_id=uploader["id"])
    try:
        uploads_service.check_article_for_misdeclared_avatars(ctx, article=article)
    finally:
        ctx.close()


def test_misdeclared_avatar_swallowed_on_redis_failure(db, uploader, monkeypatch):
    sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    _create_upload(db, uploader["id"], sha, "avatar")

    class BoomRedis:
        def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

    article = SimpleNamespace(
        id=2,
        uuid="y",
        author_id=uploader["id"],
        body=f"<img src='https://uploads.cha.fan/{sha}.png'>",
    )
    ctx = RequestContext(principal_id=uploader["id"])
    monkeypatch.setattr(ctx, "get_redis", lambda: BoomRedis())
    try:
        uploads_service.check_article_for_misdeclared_avatars(ctx, article=article)
    finally:
        ctx.close()


def test_article_read_reports_misdeclared_avatar_once(client, db, uploader, monkeypatch):
    sha = hashlib.sha256(_png(_random_rgb())).hexdigest()
    _create_upload(db, uploader["id"], sha, "avatar")
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 100)

    r = client.post(
        f"{settings.API_V1_STR}/article-columns/",
        headers=uploader["headers"],
        json={"name": f"col {get_uuid()}", "description": "test"},
    )
    assert r.status_code == 200, r.json()
    column_uuid = r.json()["uuid"]

    body = f"<img src='https://uploads.cha.fan/{sha}.png'>"
    r = client.post(
        f"{settings.API_V1_STR}/articles/",
        headers=uploader["headers"],
        json={
            "title": "figure misuse",
            "content": {"source": body, "editor": "tiptap"},
            "article_column_uuid": column_uuid,
            "is_published": True,
            "writing_session_uuid": get_uuid(),
            "visibility": "anyone",
        },
    )
    assert r.status_code == 200, r.json()
    article_uuid = r.json()["uuid"]

    reports = []
    monkeypatch.setattr(uploads_service, "report_msg", reports.append)

    assert client.get(f"{settings.API_V1_STR}/articles/{article_uuid}").status_code == 200
    assert client.get(f"{settings.API_V1_STR}/articles/{article_uuid}").status_code == 200

    assert len(reports) == 1, reports
    assert sha in reports[0]
    assert article_uuid in reports[0]
