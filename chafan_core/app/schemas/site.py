from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, validator

from chafan_core.app.schemas.preview import UserPreview
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.validators import StrippedNonEmptyBasicStr, StrippedNonEmptyStr


# Shared properties
class SiteBase(BaseModel):
    description: Optional[str]


# Properties to receive via API on creation
class SiteCreate(SiteBase):
    name: StrippedNonEmptyStr
    subdomain: StrippedNonEmptyBasicStr
    permission_type: Literal["private", "public"]
    category_topic_uuid: Optional[str] = None


# Properties to receive via API on update
class SiteUpdate(BaseModel):
    name: Optional[StrippedNonEmptyStr] = None
    description: Optional[str] = None
    category_topic_uuid: Optional[str] = None
    topic_uuids: Optional[List[str]] = None
    auto_approval: Optional[bool] = None
    min_karma_for_application: Optional[int] = None
    email_domain_suffix_for_application: Optional[str] = None
    moderator_uuid: Optional[str] = None


class SiteInDBBase(SiteBase):
    uuid: str
    name: StrippedNonEmptyStr
    subdomain: StrippedNonEmptyBasicStr
    public_readable: bool
    public_writable_question: bool
    public_writable_submission: bool
    public_writable_answer: bool
    public_writable_comment: bool
    create_question_coin_deduction: int
    addable_member: bool
    topics: List[Topic] = []
    auto_approval: bool
    min_karma_for_application: Optional[int]
    email_domain_suffix_for_application: Optional[str]

    class Config:
        from_attributes = True


# Additional properties to return via API
class Site(SiteInDBBase):
    moderator: UserPreview
    permission_type: Optional[Literal["public", "private"]] = None
    questions_count: int
    submissions_count: int
    members_count: int
    category_topic: Optional[Topic] = None

    @validator("permission_type")
    def get_permission_type(cls, v: Optional[str], values: Dict[str, Any]) -> str:
        if (
            values["public_readable"]
            and values["public_writable_question"]
            and values["public_writable_submission"]
            and values["public_writable_answer"]
            and values["public_writable_comment"]
        ):
            return "public"
        if (
            (not values["public_readable"])
            and (not values["public_writable_question"])
            and (not values["public_writable_submission"])
            and (not values["public_writable_answer"])
            and (not values["public_writable_comment"])
        ):
            return "private"
        raise Exception(f"Incompatible site flags: {values}")


# Additional properties stored in DB
class SiteInDB(SiteInDBBase):
    pass


class SiteMap(BaseModel):
    topic: Topic
    sub_site_maps: List[Any] = []
    sites: List[Site] = []


class SiteMaps(BaseModel):
    site_maps: List[SiteMap]
    sites_without_topics: List[Site]
