import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, validator
from pydantic.networks import AnyHttpUrl
from pydantic.types import SecretStr

from chafan_core.app.schemas.activity import UserFeedSettings
from chafan_core.app.schemas.preview import UserFollows, UserPreview
from chafan_core.app.schemas.profile import Profile
from chafan_core.app.schemas.richtext import RichText
from chafan_core.app.schemas.security import IntlPhoneNumber
from chafan_core.app.schemas.site import Site
from chafan_core.app.schemas.topic import Topic
from chafan_core.utils.constants import editor_T
from chafan_core.utils.validators import (
    CaseInsensitiveEmailStr,
    StrippedNonEmptyBasicStr,
    StrippedNonEmptyStr,
    validate_password,
)


# Shared properties
class UserBase(BaseModel):
    is_active: bool = True
    is_superuser: bool = False
    full_name: Optional[StrippedNonEmptyStr] = None


# Properties to receive via API on creation
class UserCreate(UserBase):
    email: CaseInsensitiveEmailStr
    password: SecretStr
    handle: Optional[StrippedNonEmptyBasicStr]

    @validator("password")
    def _valid_password(cls, v: SecretStr) -> SecretStr:
        validate_password(v)
        return v


class UserInvite(BaseModel):
    user_uuid: str
    site_uuid: str


class Invitation(BaseModel):
    id: int
    created_at: datetime.datetime
    inviter: UserPreview

    # Option 1
    invited_email: Optional[CaseInsensitiveEmailStr]
    # Option 2
    invited_user: Optional[UserPreview]

    invited_to_site: Optional[Site]
    is_sent: bool

    personal_relation: Optional[str]


class InviteIn(BaseModel):
    invite_token: str


# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[SecretStr] = None
    handle: Optional[StrippedNonEmptyStr] = None

    @validator("password")
    def _valid_password(cls, v: Optional[SecretStr]) -> Optional[SecretStr]:
        if v is not None:
            validate_password(v)
        return v


class UserWorkExperience(BaseModel):
    company_topic: Topic
    position_topic: Topic


class UserWorkExperienceInternal(BaseModel):
    company_topic_uuid: str
    position_topic_uuid: str


class UserEducationExperience(BaseModel):
    school_topic: Topic
    level: str
    major: Optional[str] = None
    enroll_year: Optional[str] = None
    graduate_year: Optional[str] = None


class UserEducationExperienceInternal(BaseModel):
    school_topic_uuid: str
    level_name: str
    major: Optional[str] = None
    enroll_year: Optional[str] = None
    graduate_year: Optional[str] = None


class UserInDBBase(UserBase):
    id: int
    uuid: str
    is_active: bool
    karma: int
    email: CaseInsensitiveEmailStr
    secondary_emails: List[CaseInsensitiveEmailStr] = []
    avatar_url: Optional[AnyHttpUrl] = None
    handle: StrippedNonEmptyBasicStr
    about: Optional[str] = None
    created_at: datetime.datetime
    residency_topics: List[Topic]
    profession_topic: Optional[Topic] = None
    remaining_coins: int
    personal_introduction: Optional[str] = None
    github_username: Optional[str] = None
    twitter_username: Optional[str] = None
    linkedin_url: Optional[AnyHttpUrl] = None
    zhihu_url: Optional[AnyHttpUrl] = None
    homepage_url: Optional[AnyHttpUrl] = None
    locale_preference: Optional[str] = None
    enable_deliver_unread_notifications: bool
    feed_settings: Optional[UserFeedSettings] = None
    default_editor_mode: editor_T

    class Config:
        from_attributes = True


class UserPublicForVisitor(UserPreview):
    gif_avatar_url: Optional[AnyHttpUrl] = None
    answers_count: int
    submissions_count: int
    questions_count: int
    articles_count: int
    created_at: datetime.datetime
    profile_view_times: int


class YearContributions(BaseModel):
    year: int
    data: List[int]


class UserPublic(UserPublicForVisitor):
    about_content: Optional[RichText]
    # deprecated
    profiles: List[Profile]
    residency_topics: List[Topic]
    profession_topics: List[Topic]
    github_username: Optional[str] = None
    twitter_username: Optional[str] = None
    linkedin_url: Optional[AnyHttpUrl] = None
    homepage_url: Optional[AnyHttpUrl] = None
    zhihu_url: Optional[AnyHttpUrl] = None
    subscribed_topics: List[Topic]
    work_exps: List[UserWorkExperience] = []
    edu_exps: List[UserEducationExperience] = []
    contributions: Optional[List[YearContributions]] = None


# Additional properties to return via API
class User(UserInDBBase):
    flag_list: List[str]
    can_create_public_site: bool
    can_create_private_site: bool
    phone_number: Optional[IntlPhoneNumber] = None


class UserQuestionSubscription(BaseModel):
    question_uuid: str
    subscription_count: int
    subscribed_by_me: bool


class UserSubmissionSubscription(BaseModel):
    submission_uuid: str
    subscription_count: int
    subscribed_by_me: bool


class UserTopicSubscription(BaseModel):
    topic_uuid: str
    subscribed_by_me: bool
    subscription_count: int


class UserAnswerBookmark(BaseModel):
    answer_uuid: str
    bookmarked_by_me: bool
    bookmarkers_count: int


class UserArticleBookmark(BaseModel):
    article_uuid: str
    bookmarked_by_me: bool
    bookmarkers_count: int


class UserUpdateSecondaryEmails(BaseModel):
    secondary_email: CaseInsensitiveEmailStr
    action: Literal["add", "remove"]
    verification_code: Optional[str]


class UserUpdatePrimaryEmail(BaseModel):
    email: CaseInsensitiveEmailStr
    verification_code: Optional[str] = None  # if from secondary


class UserUpdateLoginPhoneNumber(BaseModel):
    phone_number: IntlPhoneNumber
    verification_code: str


class UserUpdateMe(BaseModel):
    full_name: Optional[str] = None
    handle: Optional[str] = None
    about: Optional[str] = None
    default_editor_mode: Optional[editor_T] = None
    password: Optional[SecretStr] = None
    residency_topic_uuids: Optional[List[str]] = None
    profession_topic_uuids: Optional[List[str]] = None
    education_experiences: Optional[List[UserEducationExperienceInternal]] = None
    work_experiences: Optional[List[UserWorkExperienceInternal]] = None
    personal_introduction: Optional[str] = None
    github_username: Optional[str] = None
    twitter_username: Optional[str] = None
    linkedin_url: Optional[AnyHttpUrl] = None
    zhihu_url: Optional[AnyHttpUrl] = None
    homepage_url: Optional[AnyHttpUrl] = None
    flag_list: Optional[List[str]] = None
    avatar_url: Optional[AnyHttpUrl] = None
    gif_avatar_url: Optional[AnyHttpUrl] = None
    enable_deliver_unread_notifications: Optional[bool] = None

    @validator("password")
    def _valid_password(cls, v: Optional[SecretStr]) -> Optional[SecretStr]:
        if v is not None:
            validate_password(v)
        return v
