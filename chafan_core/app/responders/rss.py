from feedgen.feed import FeedGenerator

from typing import List

from chafan_core.app.models import Answer, Question, Article
from chafan_core.app.config import settings

import logging
logger = logging.getLogger(__name__)

def build_rss(contents: List, site)->str:
    """Render content items -- Answers/Questions/Articles, not Activity rows."""
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

    for content in contents:
        fe = fg.add_entry()
        verb = "内容"
        user = content.author.full_name
        if user is None or user == "":
            user ="茶饭用户"
        link = "https://cha.fan"
        description = "内容"

        if isinstance(content, Answer):
            description = content.body
            verb = "回答"
            answer = content
            question = content.question
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}/answers/{answer.uuid}"
        elif isinstance(content, Question):
            description = content.title
            verb = "提问"
            question = content
            link = f"{settings.SERVER_HOST}/questions/{question.uuid}"
        elif isinstance(content, Article):
            description = content.title + "\n\n"
            if content.body_text is not None:
                description = description + content.body_text
            verb = "文章 : " + content.title
            link = f"{settings.SERVER_HOST}/articles/{content.uuid}"
        else:
            logger.error(f"Not supported item: {content}")


        title = f"{user} 发表了{verb}"
        fe.title(title)
        fe.link(href=link)
        fe.id(link)
        fe.description(description)
        fe.author(name=user)
        fe.pubDate(content.updated_at)
    result = fg.rss_str(pretty=True)
    return result
