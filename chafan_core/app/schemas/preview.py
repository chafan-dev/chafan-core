from typing import Optional

from pydantic import BaseModel

from chafan_core.utils.validators import StrippedNonEmptyBasicStr


class SocialAnnotations(BaseModel):
    follow_follows: Optional[int] = None


class UserFollows(BaseModel):
    user_uuid: str
    followers_count: int
    followed_count: int
    followed_by_me: bool


class UserPreview(BaseModel):
    uuid: str
    handle: StrippedNonEmptyBasicStr
    full_name: Optional[str]
    avatar_url: Optional[str] = None
    personal_introduction: Optional[str] = None
    karma: int = 0
    social_annotations: SocialAnnotations = SocialAnnotations()
    follows: Optional[UserFollows] = None
