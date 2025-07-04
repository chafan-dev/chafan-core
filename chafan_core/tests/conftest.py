

# Set Mock env config
import os
mock_env = {
"DATABASE_URL" : "stub_url",
"REDIS_URL" : "stub_url",
}
for k,v in mock_env.items():
    os.environ[k] = v

# End of Mock env config

from chafan_core.app.config import settings


