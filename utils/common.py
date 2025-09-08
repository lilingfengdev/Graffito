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