from feedgen.feed import FeedGenerator

from typing import List

from chafan_core.app.models import Answer, Question
from chafan_core.app.config import settings

import logging
logger = logging.getLogger(__name__)

def build_rss(activities: List, site)->str:
    fg = FeedGenerator()
    fg.title("ChaFan RSS " + site.name)
    fg.description("Chafan RSS 圈子 " + site.name)
    fg.link(href=f"{settings.SERVER_HOST}/sites/{site.subdomain}")
    fg.id("https://cha.fan/")

    for ac in activities:
        fe = fg.add_entry()
        verb = "内容"
        user = ac.author.full_name
        if user is None or user == "":
            user ="茶饭用户"
        link = "https://cha.fan"
        description = "内容"

        if isinstance(ac, Answer):
            description = ac.body
            verb = "回答"
            answer = ac
            question = ac.question
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}/answers/{answer.uuid}"
        if isinstance(ac, Question):
            description = ac.title
            verb = "提问"
            question = ac
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}"

        title = f"{user} 发表了{verb}"
        fe.title(title)
        fe.link(href=link)
        fe.id(link)
        fe.description(description)
        fe.author(name=user)
        fe.pubDate(ac.updated_at)
    result = fg.rss_str(pretty=True)
    return result
