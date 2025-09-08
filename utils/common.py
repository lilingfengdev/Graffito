from typing import Iterable, List, TypeVar, Dict, Any

T = TypeVar("T")

def deduplicate_preserve_order(items: Iterable[T]) -> List[T]:
    """Remove duplicates while preserving original order.

    Example:
        >>> deduplicate_preserve_order([1, 2, 2, 3])
        [1, 2, 3]
    """
    seen = set()
    return [x for x in items if not (x in seen or seen.add(x))]


def to_dict(config: Any) -> Dict[str, Any]:
    """Safely convert Pydantic or dataclass config object to plain dict."""
    if config is None:
        return {}
    if hasattr(config, "model_dump"):
        return config.model_dump()
    if hasattr(config, "dict"):
        return config.dict()
    if hasattr(config, "__dict__"):
        return dict(config.__dict__)
    return dict(config) if isinstance(config, dict) else {}

# ---------- Config helpers ----------
try:
    from config import get_settings  # noqa: F401 – Optional if config exists
except Exception:  # pragma: no cover
    # Allow utils.common to be imported without config available (during early stage)
    get_settings = None  # type: ignore


def get_platform_config(platform_key: str) -> Dict[str, Any]:
    """Return publisher config dict for given platform key.

    Example:
        >>> cfg = get_platform_config("qzone")
    """
    if get_settings is None:
        return {}
    try:
        settings = get_settings()
        cfg = settings.publishers.get(platform_key)
        return to_dict(cfg)
    except Exception:
        return {}