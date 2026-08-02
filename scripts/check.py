from dotenv import load_dotenv  # isort:skip

load_dotenv()  # isort:skip

from chafan_core.app.common import EVENT_TEMPLATES
from chafan_core.app.schemas.event import Event, EventInternal
from chafan_core.app.services.activity_policy import POLICY


def _verbs_of(model) -> set:
    verbs = set()
    for k, v in model.model_json_schema()["$defs"].items():
        if k == "ContentVisibility":
            continue
        if "properties" not in v:
            raise Exception(f"{k}: {v}")
        if "verb" in v["properties"]:
            verbs.add(v["properties"]["verb"]["default"])
    return verbs


_event_verbs = _verbs_of(Event)

assert set(EVENT_TEMPLATES.keys()) == _event_verbs, set(
    EVENT_TEMPLATES.keys()
).symmetric_difference(_event_verbs)

print(f"Checked _event_verbs: {sorted(_event_verbs)}")

# Every verb that can be written must have a row in the policy table, so that
# adding an event forces a decision about its sinks instead of defaulting to
# "goes nowhere" silently.
_internal_verbs = _verbs_of(EventInternal)

assert set(POLICY.keys()) == _internal_verbs, set(POLICY.keys()).symmetric_difference(
    _internal_verbs
)

print(f"Checked activity_policy verbs: {len(POLICY)}")
