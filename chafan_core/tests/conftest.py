from pytest_trio.enable_trio_mode import *

# Set Mock env config (only if not already set)
import os
mock_env = {
"DATABASE_URL" : "stub_url",
"REDIS_URL" : "stub_url",
"SERVER_HOST" : "stub_server_host",
}
for k,v in mock_env.items():
    if k not in os.environ:
        os.environ[k] = v

# End of Mock env config

from chafan_core.app.config import settings


