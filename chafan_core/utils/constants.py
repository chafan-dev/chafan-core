from typing import Literal, Mapping, Union

MAX_ARCHIVE_PAGINATION_LIMIT = 10
MAX_SITE_QUESTIONS_PAGINATION_LIMIT = 20
MAX_SITE_SUBMISSIONS_PAGINATION_LIMIT = 20
MAX_USER_QUESTIONS_PAGINATION_LIMIT = 20
MAX_USER_SUBMISSIONS_PAGINATION_LIMIT = 20
MAX_USER_ARTICLES_PAGINATION_LIMIT = 20
MAX_USER_ANSWERS_PAGINATION_LIMIT = 20
MAX_MY_SUBSCRIBED_ITEMS_PAGINATION_LIMIT = 20
MAX_USER_FOLLOWERS_PAGINATION_LIMIT = 20
MAX_USER_FOLLOWED_PAGINATION_LIMIT = 20
MAX_FEATURED_ANSWERS_LIMIT = 20

# Why storing editor choice? Pre-rendering for email etc.

editor_T = Literal[
    "tiptap",
    "wysiwyg",  # vditor WYSIWYG mode
    "markdown",  # deprecated -- not used in prod frontend
    "markdown_splitview",  # vditor SV mode
    "markdown_realtime_rendering",  # vditor IR mode
]
indexed_object_T = Literal["question", "answer", "article", "submission", "site"]


feedback_status_T = Union[
    Literal["sent"], Literal["processing"], Literal["closed"], Literal["wontfix"]
]

feedback_status_in_zhCN: Mapping[feedback_status_T, str] = {
    "sent": "已收到",
    "processing": "处理中",
    "closed": "已解决",
    "wontfix": "暂不解决",
}
