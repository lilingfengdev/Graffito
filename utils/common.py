from typing import Iterable, List, TypeVar, Dict, Any
from pathlib import Path
import yaml

try:
    from nonebot.utils import deep_update
except ImportError:
    # 如果 NoneBot 不可用，使用自定义实现
    def deep_update(base: dict, *updates: dict) -> dict:
        """Fallback implementation of deep_update"""
        for update in updates:
            for k, v in update.items():
                if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                    base[k] = deep_update(base[k], v)
                else:
                    base[k] = v
        return base

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
            if isinstance(override_data, dict):
                base = deep_update(base, override_data)
    except Exception:
        # best-effort merge; ignore malformed override files
        pass

    return base


# ---------- Cache key helpers ----------
def make_cache_key(prefix: str, *parts: Any) -> str:
    """生成标准格式的缓存键
    
    Args:
        prefix: 缓存键前缀（如 'submission', 'blacklist' 等）
        *parts: 缓存键的组成部分
        
    Returns:
        格式化的缓存键，如 'submission:123' 或 'blacklist:user123:group1'
    """
    key_parts = [prefix] + [str(part) for part in parts if part is not None]
    return ':'.join(key_parts)