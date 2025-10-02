"""CLI适配器模块"""

from .base_adapter import BaseCliAdapter
from .generic_adapter import GenericAdapter

__all__ = [
    'BaseCliAdapter',
    'GenericAdapter'
]