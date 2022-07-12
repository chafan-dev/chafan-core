import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Mapping

import sentry_sdk
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import ASYNCHRONOUS, SYNCHRONOUS

from chafan_core.app.common import is_dev
from chafan_core.app.config import settings


class MetricsClient(object):
    def __init__(
        self,
        tags: Mapping[str, str] = {},
        disabled: bool = False,
        async_mode: bool = True,
    ) -> None:
        self.async_mode = async_mode
        if is_dev() or disabled:
            self.disabled = disabled
            return None
        self.disabled = False
        try:
            self.client = InfluxDBClient(
                url=settings.INFLUXDB_URL, token=settings.INFLUXDB_TOKEN
            )
            self.tags = tags
        except Exception as e:
            # Disable if exception in initialization
            sentry_sdk.capture_exception(e)
            self.disabled = True

    def write(self, point_name: str, field_name: str, value: float) -> None:
        if is_dev() or self.disabled:
            return None
        try:
            write_options = ASYNCHRONOUS
            if not self.async_mode:
                write_options = SYNCHRONOUS
            write_api = self.client.write_api(write_options=write_options)
            point = Point(point_name)
            for k, v in self.tags.items():
                point = point.tag(k, v)
            point = point.field(field_name, value).time(
                datetime.utcnow(), WritePrecision.NS
            )
            write_api.write(settings.INFLUXDB_BUCKET, settings.INFLUXDB_ORG, point)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            return None

    def close(self) -> None:
        if is_dev() or self.disabled:
            return None
        self.client.close()

    @contextmanager
    def measure_duration(self, point_name: str) -> Any:
        now = time.time()
        try:
            yield None
        finally:
            self.write(point_name, "duration_seconds", time.time() - now)


metrics_client_serve = MetricsClient(tags={"mode": "serve"}, async_mode=True)
metrics_client_batch = MetricsClient(tags={"mode": "batch"}, async_mode=False)
