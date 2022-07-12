from typing import Literal, Mapping, Set

from pydantic import BaseModel

ReactionObjectType = Literal["question", "answer", "comment", "article", "submission"]


class Reaction(BaseModel):
    object_uuid: str
    object_type: ReactionObjectType
    reaction: Literal["👍", "👎", "👀", "❤️", "😂", "🙏"]
    action: Literal["add", "cancel"]


class Reactions(BaseModel):
    counters: Mapping[str, int]
    my_reactions: Set[str]
