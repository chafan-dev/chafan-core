import os
import subprocess

from chafan_core.app.config import settings

env = os.environ.copy()
env["DATABASE_URL"] = settings.DATABASE_URL

subprocess.check_call(["alembic", "upgrade", "head"], env=env)
