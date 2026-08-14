import hashlib
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.orm import Session

from chafan_core.app import crud, image_sanitize, karma, models, object_storage, rules
from chafan_core.app.config import settings
from chafan_core.tests.utils.user import authentication_token_from_email
from chafan_core.tests.utils.utils import random_email

UPLOAD_BASE = "https://uploads.cha.fan"


def _png(rgb=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), rgb).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg(rgb=(10, 20, 30), description=None, gps=False) -> bytes:
    img = Image.new("RGB", (20, 20), rgb)
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
    f1 = Image.new("RGB", (10, 10), (255, 0, 0))
    f2 = Image.new("RGB", (10, 10), (0, 255, 0))
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
    data = _png(rgb=(0, 128, 255))

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
    data = _jpeg(rgb=(30, 40, 50), description="GPS location of my house", gps=True)
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
    a = _jpeg(rgb=(60, 70, 80), description="first copy")
    b = _jpeg(rgb=(60, 70, 80), description="second copy")

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
    data = _png(rgb=(1, 2, 3))

    r = _upload(client, uploader["headers"], data, purpose="figure")
    assert r.status_code == 403, r.json()

    r = _upload(client, uploader["headers"], data, purpose="avatar")
    assert r.status_code == 200, r.json()


def test_zero_coins(client, db, uploader, fake_put_image):
    _set_karma(db, uploader["id"], 100)
    _set_coins(db, uploader["id"], 0)
    data = _png(rgb=(9, 8, 7))

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
