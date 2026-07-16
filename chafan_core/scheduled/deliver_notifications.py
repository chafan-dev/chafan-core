from chafan_core.app.infra.runtime import execute_with_broker
from chafan_core.scheduled.lib import deliver_notifications


def run_deliver_notification_task() -> None:
    print("run_deliver_notification_task", flush=True)
    execute_with_broker(deliver_notifications)
