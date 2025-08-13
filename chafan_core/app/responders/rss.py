from feedgen.feed import FeedGenerator

from typing import List

from chafan_core.app.models import Answer, Question, Article
from chafan_core.app.config import settings

import logging
logger = logging.getLogger(__name__)

def build_rss(activities: List, site)->str:
    fg = FeedGenerator()
    if site is not None:
        fg.title("ChaFan RSS " + site.name)
        fg.description("Chafan RSS 圈子 " + site.name)
        fg.link(href=f"{settings.SERVER_HOST}/sites/{site.subdomain}")
    else:
        fg.title("ChaFan RSS - no specific site")
        fg.description("Chafan RSS 不限圈子 ")
        fg.link(href=f"{settings.SERVER_HOST}")
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
        elif isinstance(ac, Question):
            description = ac.title
            verb = "提问"
            question = ac
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}"
        elif isinstance(ac, Article):
            print(ac.__dict__)
            description = ac.title + "\n\n"
            if ac.body_text is not None:
                description = description + ac.body_text
            verb = "文章 : " + ac.title
            link = f"{settings.SERVER_HOST}/articles/{ac.uuid}"
        else:
            logger.error(f"Not supported item: {ac}")


        title = f"{user} 发表了{verb}"
        fe.title(title)
        fe.link(href=link)
        fe.id(link)
        fe.description(description)
        fe.author(name=user)
        fe.pubDate(ac.updated_at)
    result = fg.rss_str(pretty=True)
    return result
