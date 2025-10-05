"""
AISwitch - AI API环境切换工具

一个轻量级的命令行工具，用于快速切换不同AI API服务提供商的环境配置。
"""

__version__ = "0.1.0"
__author__ = "AISwitch Contributors"
__email__ = "aiswitch@example.com"
__description__ = "A lightweight command-line tool for switching between different AI API service providers"

from .config import ConfigManager, PresetConfig, GlobalConfig, ProjectConfig
from .env import EnvManager
from .preset import PresetManager
from .utils import (
    is_valid_preset_name,
    is_valid_url,
    normalize_url,
    mask_sensitive_value,
    get_system_info,
)

__all__ = [
    "ConfigManager",
    "PresetConfig",
    "GlobalConfig",
    "ProjectConfig",
    "EnvManager",
    "PresetManager",
    "is_valid_preset_name",
    "is_valid_url",
    "normalize_url",
    "mask_sensitive_value",
    "get_system_info",
]
