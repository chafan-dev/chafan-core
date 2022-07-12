import os
import time

import sentry_sdk
from botocore.exceptions import ClientError

from chafan_core.app.aws import get_sns_client
from chafan_core.app.common import is_dev


def send_sms(phone_number: str, msg: str) -> None:
    if not is_dev():
        try:
            ses = get_sns_client()
            ses.publish(
                PhoneNumber=phone_number,
                Message=msg,
            )
        except ClientError as e:
            sentry_sdk.capture_exception(e)
    else:
        inbox_dir = f"/tmp/chafan/sms-inbox/{phone_number}"
        os.makedirs(inbox_dir, exist_ok=True)
        with open(inbox_dir + f"/{int(time.time())}.txt", "w") as f:
            f.write(msg)
