import re

STOP = set(
    "a an the is are was were be been being of in on at to for from with and or "
    "it its this that these those what which how why does do did can could would "
    "should about across describe explain compare comparison approaches techniques "
    "documents document paper papers say said they their them me please".split()
)


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[\w]+", text.lower()) if w not in STOP and len(w) > 1]


def token_bound(text: str) -> int:
    """Conservative UTF-8 byte bound, not a model-specific token count."""
    return len(text.encode("utf-8"))
