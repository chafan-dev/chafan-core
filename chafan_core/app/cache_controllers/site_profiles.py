from typing import List

from chafan_core.app import crud, models, schemas
from chafan_core.app.cached_layer import CachedLayer
from chafan_core.app.recs.ranking import rank_site_profiles

USER_SITE_PROFILES = "chafan:{user_id}:site-profiles"


class CachedSiteProfiles(CachedLayer):
    def get_site_profiles(self) -> List[schemas.Profile]:
        user_id = self.unwrapped_principal_id()
        db = self.get_db()

        def f() -> List[schemas.Profile]:
            current_user = crud.user.get(db, id=user_id)
            assert current_user is not None
            return [
                self.materializer.profile_schema_from_orm(p)
                for p in rank_site_profiles(current_user.profiles)
            ]

        return self._get_cached(
            key=USER_SITE_PROFILES.format(user_id=user_id),
            typeObj=List[schemas.Profile],
            fetch=f,
            hours=24,
        )

    def create_site_profile(
        self, *, owner: models.User, site_uuid: str
    ) -> schemas.Profile:
        data = crud.profile.create_with_owner(
            self.get_db(),
            obj_in=schemas.ProfileCreate(
                owner_uuid=owner.uuid,
                site_uuid=site_uuid,
            ),
        )
        self.get_redis().delete(USER_SITE_PROFILES.format(user_id=owner.id))
        return self.materializer.profile_schema_from_orm(data)

    def remove_site_profile(self, *, owner_id: int, site_id: int) -> None:
        crud.profile.remove_by_user_and_site(
            self.get_db(), owner_id=owner_id, site_id=site_id
        )
        self.get_redis().delete(USER_SITE_PROFILES.format(user_id=owner_id))
