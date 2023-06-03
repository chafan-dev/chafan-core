import hashlib
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import AnyHttpUrl
from pydantic.tools import parse_obj_as

from chafan_core.app import schemas
from chafan_core.app.api import deps
from chafan_core.app.aws import get_s3_client
from chafan_core.app.common import is_dev, valid_content_length
from chafan_core.app.config import settings
from chafan_core.utils.base import HTTPException_, unwrap

router = APIRouter()


@router.post("/images/", response_model=schemas.UploadedImage)
def upload_image(
    file: UploadFile = File(...),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
    file_size: int = Depends(valid_content_length),
) -> Any:
    if is_dev():
        return schemas.UploadedImage(url="https://picsum.photos/200/300")
    else:
        if not current_user_id:
            raise HTTPException_(
                status_code=400,
                detail="Upload requires login.",
            )
    assert settings.AWS_CLOUDFRONT_HOST is not None
    s3 = get_s3_client()
    tmpfile_name = None
    h = hashlib.sha256()
    with NamedTemporaryFile(delete=False) as tmpfile:
        written_size = 0
        while written_size < file_size:
            chunk = file.file.read(file_size - written_size)
            if len(chunk) == 0:
                break
            written_size += len(chunk)
            tmpfile.write(chunk)
            h.update(chunk)
        tmpfile_name = tmpfile.name
    key = h.hexdigest()
    s3.upload_file(
        tmpfile_name,
        settings.S3_UPLOADS_BUCKET_NAME,
        key,
        ExtraArgs={"CacheControl": "max-age=360000"},
    )
    return schemas.UploadedImage(url=f"{settings.AWS_CLOUDFRONT_HOST}/{key}")


@router.post("/vditor/", response_model=schemas.msg.UploadResults)
def upload_files_from_vditor(
    files: List[UploadFile] = File(...),
    current_user_id: Optional[int] = Depends(deps.try_get_current_user_id),
    file_size: int = Depends(valid_content_length),
) -> Any:
    if is_dev():
        return schemas.msg.UploadResults(
            data=schemas.msg.UploadResultData(
                succMap={
                    "example.jpeg": parse_obj_as(
                        AnyHttpUrl, "https://picsum.photos/200/300"
                    )
                }
            )
        )
    else:
        if not current_user_id:
            raise HTTPException_(
                status_code=400,
                detail="Upload requires login.",
            )
    assert settings.AWS_CLOUDFRONT_HOST is not None
    s3 = get_s3_client()
    succMap: Dict[str, AnyHttpUrl] = {}
    for file in files:
        tmpfile_name = None
        h = hashlib.sha256()
        with NamedTemporaryFile(delete=False) as tmpfile:
            written_size = 0
            while written_size < file_size:
                chunk = file.file.read(file_size - written_size)
                if len(chunk) == 0:
                    break
                written_size += len(chunk)
                tmpfile.write(chunk)
                h.update(chunk)
            tmpfile_name = tmpfile.name
        key = h.hexdigest()
        s3.upload_file(
            tmpfile_name,
            settings.S3_UPLOADS_BUCKET_NAME,
            key,
            ExtraArgs={"CacheControl": "max-age=360000"},
        )
        succMap[unwrap(file.filename)] = parse_obj_as(
            AnyHttpUrl, f"{settings.AWS_CLOUDFRONT_HOST}/{key}"
        )
    return schemas.msg.UploadResults(data=schemas.msg.UploadResultData(succMap=succMap))
