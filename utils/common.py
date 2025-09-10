from typing import Iterable, List, TypeVar, Dict, Any
from pathlib import Path
import yaml

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
    """Return merged publisher config dict for given platform key.

    Priority (later overrides earlier):
      1) settings.publishers[platform_key] from main config
      2) config/publishers/{platform_key}.yml if exists
    """
    def deep_merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        for k, v in (override or {}).items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                base[k] = deep_merge_dict(dict(base[k]), dict(v))
            else:
                base[k] = v
        return base

    if get_settings is None:
        base: Dict[str, Any] = {}
    else:
        try:
            settings = get_settings()
            cfg = settings.publishers.get(platform_key)
            base = to_dict(cfg)
        except Exception:
            base = {}

    # Merge per-publisher YAML overrides
    try:
        override_path = Path(f"config/publishers/{platform_key}.yml")
        if not override_path.exists():
            override_path = Path(f"config/publishers/{platform_key}.yaml")
        if override_path.exists():
            with open(override_path, 'r', encoding='utf-8') as f:
                override_data = yaml.safe_load(f) or {}
            base = deep_merge_dict(base, override_data if isinstance(override_data, dict) else {})
    except Exception:
        # best-effort merge; ignore malformed override files
        pass

    return base