"""Shared helpers for responders that accept PrincipalView or RequestContext."""


def shaper(ctx):
    """Return the PrincipalView-like object for nested previews/comments.

    RequestContext has .principal_view; PrincipalView is itself the shaper.
    """
    return getattr(ctx, "materializer", ctx)


def get_db(ctx):
    if hasattr(ctx, "get_db"):
        return ctx.get_db()
    return ctx.broker.get_db()
