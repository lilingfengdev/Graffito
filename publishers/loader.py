"""Dynamic publisher discovery and registration utilities.

This module scans the `publishers` package for subclasses of `BasePublisher`,
derives their platform key from the package path (e.g. publishers.qzone.* -> qzone),
and registers enabled publishers based on merged configuration (including per-publisher YAML overrides).
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType
from typing import Dict, Optional, Type

from core.plugin import plugin_manager
from core.enums import PublishPlatform
from publishers.base import BasePublisher
from utils.common import get_platform_config


def _derive_platform_key_from_module(module_name: str) -> Optional[str]:
    """Derive platform key from module name like 'publishers.qzone.publisher'."""
    parts = module_name.split('.')
    try:
        idx = parts.index('publishers')
    except ValueError:
        return None
    if len(parts) > idx + 1:
        key = parts[idx + 1]
        return key
    return None


def discover_publisher_classes() -> Dict[str, Type[BasePublisher]]:
    """Discover all BasePublisher subclasses under the publishers package.

    Returns a mapping of platform_key -> Publisher class.
    """
    import publishers as publishers_pkg  # local import to ensure package is available

    discovered: Dict[str, Type[BasePublisher]] = {}
    for finder, name, ispkg in pkgutil.walk_packages(publishers_pkg.__path__, publishers_pkg.__name__ + "."):
        # Skip utility modules
        if name.endswith('.base') or name.endswith('.loader'):
            continue
        try:
            module: ModuleType = importlib.import_module(name)
        except Exception:
            # Best-effort discovery: ignore modules that fail to import
            continue

        platform_key = _derive_platform_key_from_module(name)
        if not platform_key:
            continue

        # Validate against known platforms if possible
        known_values = {p.value for p in PublishPlatform}
        if platform_key not in known_values:
            # Allow unknown for forward compatibility but prefer known values
            pass

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BasePublisher) or obj is BasePublisher:
                continue
            # If multiple classes found under same platform, the last one wins (usually only one)
            discovered[platform_key] = obj  # type: ignore[assignment]
    return discovered


def register_publishers_from_configs() -> Dict[str, BasePublisher]:
    """Instantiate and register enabled publishers based on merged configs.

    Returns a mapping of plugin name -> instance.
    """
    classes = discover_publisher_classes()
    instances: Dict[str, BasePublisher] = {}
    for platform_key, cls in classes.items():
        cfg = get_platform_config(platform_key) or {}
        if not bool(cfg.get('enabled', False)):
            continue
        try:
            instance: BasePublisher = cls(cfg)  # type: ignore[call-arg]
            plugin_manager.register(instance)
            instances[instance.name] = instance
        except Exception:
            # Skip invalid publishers but do not crash the app
            continue
    return instances

