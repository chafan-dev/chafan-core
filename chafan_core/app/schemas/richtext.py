from typing import Optional

from pydantic import BaseModel

from chafan_core.utils.constants import editor_T


class RichText(BaseModel):
    source: str
    rendered_text: Optional[str] = None
    editor: editor_T
