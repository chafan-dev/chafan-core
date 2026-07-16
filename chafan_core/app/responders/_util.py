"""Shared helpers for responders that accept Materializer or RequestContext."""


def shaper(ctx):
    """Return the Materializer-like object for nested previews/comments.

    RequestContext has .materializer; Materializer is itself the shaper.
    """
    return getattr(ctx, "materializer", ctx)


def get_db(ctx):
    if hasattr(ctx, "get_db"):
        return ctx.get_db()
    return ctx.broker.get_db()
