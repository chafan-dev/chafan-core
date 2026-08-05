"""Create the smoke test site and its article columns.

The site acts as a realistic community hub -- a technology-focused platform
with distinct content sections (columns) for different types of posts.
"""
from __future__ import annotations

from chafan_core.app import crud, models, schemas
from chafan_core.app.schemas.profile import ProfileCreate
from chafan_core.utils.validators import StrippedNonEmptyBasicStr, StrippedNonEmptyStr

SITE_SUBDOMAIN = "smoke"
SITE_NAME = "Smoke Test Community"
SITE_DESCRIPTION = (
    "A vibrant technology community for developers, designers, and data "
    "scientists to share knowledge, ask questions, and publish articles."
)


def _get_or_create_site(db, moderator):
    """Get existing site or create it with the moderator as owner."""
    site = crud.site.get_by_subdomain(db, subdomain=SITE_SUBDOMAIN)
    if site:
        return site
    site_in = schemas.SiteCreate(
        name=StrippedNonEmptyStr(SITE_NAME),
        subdomain=StrippedNonEmptyBasicStr(SITE_SUBDOMAIN),
        permission_type="public",
        description=StrippedNonEmptyStr(SITE_DESCRIPTION),
    )
    return crud.site.create_with_permission_type(
        db, obj_in=site_in, moderator=moderator, category_topic_id=None
    )


def _ensure_membership(db, site, user) -> models.Profile | None:
    """Ensure user has a profile on this site."""
    existing = crud.profile.get_by_user_and_site(db, owner_id=user.id, site_id=site.id)
    if existing:
        return existing
    return crud.profile.create_with_owner(
        db,
        obj_in=schemas.ProfileCreate(site_uuid=site.uuid, owner_uuid=user.uuid),
    )


# ---------------------------------------------------------------------------
# Article column definitions -- realistic section names
# ---------------------------------------------------------------------------

COLUMNS = [
    {
        "key": "column_a",
        "name": "Engineering Deep Dives",
        "description": "Long-form technical articles about architecture, systems design, and implementation details.",
    },
    {
        "key": "column_b",
        "name": "Quick Tips & Tricks",
        "description": "Short, actionable tips for everyday development. From CLI hacks to debugging strategies.",
    },
    {
        "key": "column_c",
        "name": "Community Updates",
        "description": "Announcements, changelogs, and retrospectives from the community.",
    },
]


def _get_or_create_column(db, owner, spec: dict):
    """Get existing column or create a new one."""
    existing = (
        crud.article_column.get_by_name(db, name=spec["name"])
        if hasattr(crud.article_column, "get_by_name")
        else None
    )
    if existing:
        return existing

    # Check if owner already has a column with this name
    for col in getattr(owner, "article_columns", []) or []:
        if col.name == spec["name"]:
            return col

    return crud.article_column.create_with_owner(
        db,
        obj_in=schemas.ArticleColumnCreate(
            name=StrippedNonEmptyStr(spec["name"]),
            description=spec.get("description"),
        ),
        owner_id=owner.id,
    )


def build_site_and_columns(db, account_a) -> tuple:
    """Create site, ensure memberships, create columns.

    Returns (site, column_a, column_b, column_c).
    """
    site = _get_or_create_site(db, account_a)
    for key in ["account_a", "account_b"]:
        _ensure_membership(db, site, account_a)

    columns = {}
    for spec in COLUMNS:
        columns[spec["key"]] = _get_or_create_column(db, account_a, spec)

    db.flush()
    return site, columns["column_a"], columns["column_b"], columns["column_c"]
