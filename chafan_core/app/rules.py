"""The rules of Chafan: every number that decides karma and coins.

You do not need to know Python to change anything in this file. Each rule is
one line of the form `NAME = number`, with a comment saying what it does. If
you think a number is unfair, edit it, open a pull request, and say why.

This file is deliberately plain data. It imports nothing and computes nothing,
so there is no hidden behaviour to read around. The code that applies these
rules lives in `karma.py` (karma) and `coins.py` (coins).

Two separate systems, often confused:

  * **Karma** is a score. It measures what you have contributed, it is never
    spent, and it is the same number everywhere on the site.
  * **Coins** are anti-spam credit. They are spent and earned, and they are
    not money -- they cannot be bought or cashed out.
"""

# ---------------------------------------------------------------------------
# Karma you earn by contributing
#
# Each piece of content earns a flat amount for writing it, plus an amount for
# every upvote it receives. Content that is deleted, hidden by a moderator, or
# still an unpublished draft earns nothing -- so karma is taken back if a
# post is later removed.
# ---------------------------------------------------------------------------

ANSWER_CREATE = 10  # writing an answer (counted when you publish, not while drafting)
ANSWER_UPVOTE = 10  # each upvote your answer receives

QUESTION_CREATE = 5  # asking a question
QUESTION_UPVOTE = 10  # each upvote your question receives

ARTICLE_CREATE = 5  # writing an article (counted when you publish it)
ARTICLE_UPVOTE = 10  # each upvote your article receives

SUBMISSION_CREATE = 1  # sharing a link
SUBMISSION_UPVOTE = 2  # each upvote your link receives

COMMENT_CREATE = 2  # writing a comment (comment upvotes earn nothing today)


# ---------------------------------------------------------------------------
# Karma you earn by filling in your profile
#
# A one-time reward for telling people who you are. There are ten profile
# fields: full name, GitHub, Twitter, LinkedIn, homepage, Zhihu, avatar,
# animated avatar, and personal introduction.
# ---------------------------------------------------------------------------

PROFILE_FIELD = 2  # each profile field you fill in
EXPERIENCE_PER_ITEM = 2  # each work or education entry you add
EXPERIENCE_MAX_ITEMS = 5  # only the first five of each are rewarded


# ---------------------------------------------------------------------------
# What karma unlocks
# ---------------------------------------------------------------------------

MIN_KARMA_CREATE_SITE = 100  # karma needed to create a site without admin approval
MIN_KARMA_UPLOAD_IMAGE = 100  # karma needed to put a picture in an article or answer


# ---------------------------------------------------------------------------
# Coins
#
# Coins slow down spam by putting a small price on actions that are cheap to
# automate and expensive for everyone else to read. Most costs below are paid
# to another person, not burned: upvoting an article pays its author, creating
# a site pays the site admin, and inviting someone pays you. UPLOAD_IMAGE_COST
# is the exception -- it is burned, because storage has no counterparty to pay.
# ---------------------------------------------------------------------------

INITIAL_USER_COINS = 0  # coins a brand new account starts with
# TODO: 0 with no organic way to earn coins means a new account can never
# afford any coin cost (CREATE_ARTICLE_COST, UPLOAD_IMAGE_COST, ...). Fix this
# as its own change; do not paper over it here.

CREATE_ARTICLE_COST = 2  # writing an article, paid to the site admin
UPVOTE_ARTICLE_COST = 2  # upvoting an article, paid to the article's author
CREATE_SITE_COST = 10  # creating a site, paid to the site admin
UPLOAD_IMAGE_COST = 2  # uploading a new picture; the same picture again is free

INVITE_NEW_USER_REWARD = 5  # paid to you by the site admin for each person you invite
INVITE_NEW_USER_MAX_REWARDED = 10  # only your first ten invitations are rewarded
