from enum import Enum
from typing import List, Mapping, Optional

from pydantic import BaseModel
from pydantic.networks import AnyHttpUrl

from chafan_core.utils.validators import StrippedNonEmptyBasicStr


class Scores(BaseModel):
    full_score: int
    score: int


class ClaimWelcomeTestScoreMsg(BaseModel):
    success: bool
    scores: Scores


class UploadResultData(BaseModel):
    errFiles: List[str] = []
    succMap: Mapping[str, AnyHttpUrl]


class UploadResults(BaseModel):
    msg: str = ""
    code: int = 0
    data: UploadResultData


class HealthResponse(BaseModel):
    success: bool = True
    version: str = "v0.1.0"


class WsAuthResponse(BaseModel):
    token: str


class ErrorCode(str, Enum):
    pass


class GenericResponse(BaseModel):
    success: bool = True
    error_code: Optional[ErrorCode] = None
    msg: Optional[str] = None


class UploadedImage(BaseModel):
    url: str


class SiteApplicationResponse(BaseModel):
    auto_approved: bool = False
    applied_before: bool = False


class VerifyTelegramResponse(BaseModel):
    handle: StrippedNonEmptyBasicStr
