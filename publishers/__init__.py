"""发送器插件包

仅暴露基础类型，避免对子包的强耦合导入。具体发送器由动态发现加载。
"""
from .base import BasePublisher  # noqa: F401

__all__ = ['BasePublisher']
