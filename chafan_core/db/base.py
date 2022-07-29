# Import all the models, so that Base has them before being
# imported by Alembic
from chafan_core.app.models.user import User  # noqa
from chafan_core.db.base_class import Base  # noqa
