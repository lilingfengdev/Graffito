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
    """Discover BasePublisher subclasses that are enabled by config.

    Priority:
      1) For each known platform in PublishPlatform, if config says enabled,
         import 'publishers.<key>.publisher' directly and collect classes.
      2) Fallback to pkgutil walk if nothing found (best-effort).

    Returns mapping of platform_key -> Publisher class.
    """
    discovered: Dict[str, Type[BasePublisher]] = {}

    # Prefer explicit import of enabled platforms to avoid importing unrelated/heavy modules
    for p in PublishPlatform:
        key = p.value
        cfg = get_platform_config(key) or {}
        if not bool(cfg.get('enabled', False)):
            continue
        try:
            module: ModuleType = importlib.import_module(f"publishers.{key}.publisher")
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePublisher) and obj is not BasePublisher:
                    discovered[key] = obj  # type: ignore[assignment]
                    break
        except Exception:
            # Skip modules that fail to import; continue discovering others
            continue

    if discovered:
        return discovered

    # Fallback: generic walk (may import disabled or heavy modules; kept for backward compatibility)
    import publishers as publishers_pkg  # local import to ensure package is available
    for _, name, ispkg in pkgutil.walk_packages(publishers_pkg.__path__, publishers_pkg.__name__ + "."):
        if name.endswith('.base') or name.endswith('.loader'):
            continue
        try:
            module: ModuleType = importlib.import_module(name)
        except Exception:
            continue
        platform_key = _derive_platform_key_from_module(name)
        if not platform_key:
            continue
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BasePublisher) and obj is not BasePublisher:
                discovered[platform_key] = obj  # type: ignore[assignment]
                break
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

