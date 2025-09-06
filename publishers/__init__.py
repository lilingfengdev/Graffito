"""发送器插件模块"""
from .base import BasePublisher
from .qzone import QzonePublisher

__all__ = ['BasePublisher', 'QzonePublisher']
