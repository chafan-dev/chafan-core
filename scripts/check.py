from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

from chafan_core.app.common import EVENT_TEMPLATES
from chafan_core.app.schemas.event import Event

_event_verbs = []

for k, v in Event.model_json_schema()["$defs"].items():
    if k == "ContentVisibility":
        continue
    if "properties" not in v:
        raise Exception(f"{k}: {v}")
    if "verb" in v["properties"]:
        _event_verbs.append(v["properties"]["verb"]["default"])

assert set(EVENT_TEMPLATES.keys()) == set(_event_verbs), set(
    EVENT_TEMPLATES.keys()
).symmetric_difference(set(_event_verbs))

print(f"Checked _event_verbs: {_event_verbs}")
