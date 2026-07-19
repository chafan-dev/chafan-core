# Deferred: ErrorMsg Literal Union → StrEnum

**Source:** v1 `proposals/09-error-msg-enum.md`.

**Status:** Dropped unless maintenance pain becomes concrete.

---

## Summary of the proposal

Convert `ErrorMsg` in `chafan_core/utils/base.py` from:

```python
ErrorMsg = Union[
    Literal["Unauthorized"],
    Literal["The topic doesn't exist in the system."],
    # ... 129 more
]
```

to:

```python
class ErrorMsg(StrEnum):
    UNAUTHORIZED = "Unauthorized"
    TOPIC_NOT_FOUND = "The topic doesn't exist in the system."
    # ...
```

Replace every literal string at call sites with `ErrorMsg.X`.

## Why dropped

- 50–80 file diff. Every endpoint that calls `HTTPException_` needs to change.
- Large mechanical diff creates merge conflicts across in-flight branches.
- `git blame` gets disrupted across every endpoint file.
- The existing `Literal` union is already mypy-checked. There is no correctness gap.
- Searchability is already fine: `grep "The question doesn't exist"` works.
- The real bug (malformed `"error_msg,"`, grammar typos) is fixed by `03-grammar-fixes.md`, which is in v2.

The remaining benefit — IDE autocomplete — is a DX improvement that doesn't justify the refactor cost.

## Trigger for revisiting

- Someone introduces another typo in a literal string that mypy can't catch (e.g. because they copy-paste a slightly different string).
- Adding a new error message proves awkward in practice (needs autocomplete to discover existing ones).
- A clean window opens where no other in-flight branches would be disrupted by the 50–80 file diff.

Until then, the Literal union stays.
