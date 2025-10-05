import os
import sys
import platform
from pathlib import Path
from typing import Dict, List, Optional, Union
import re


def is_valid_preset_name(name: str) -> bool:
    """验证预设名称是否有效"""
    if not name or not name.strip():
        return False

    if len(name) > 50:
        return False

    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return False

    if name.startswith(".") or name.startswith("-"):
        return False

    return True


def is_valid_url(url: str) -> bool:
    """验证URL是否有效"""
    if not url:
        return False

    url_pattern = re.compile(
        r"^https?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
        r"(?::\d+)?"  # optional port
        r"(?:/?|[/?]\S+)$",
        re.IGNORECASE,
    )

    return url_pattern.match(url) is not None


def normalize_url(url: str) -> str:
    """规范化URL格式"""
    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if url.endswith("/"):
        url = url.rstrip("/")

    return url


def mask_sensitive_value(value: str, mask_char: str = "*") -> str:
    """遮盖敏感信息"""
    if len(value) <= 8:
        return mask_char * len(value)

    visible_chars = 4
    return (
        value[:visible_chars]
        + mask_char * (len(value) - visible_chars * 2)
        + value[-visible_chars:]
    )


def get_system_info() -> Dict[str, str]:
    """获取系统信息"""
    return {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version.split()[0],
        "architecture": platform.machine(),
        "shell": os.environ.get("SHELL", "unknown"),
    }


def ensure_directory_exists(path: Union[str, Path]) -> Path:
    """确保目录存在，如果不存在则创建"""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_file_operation(operation_func, *args, **kwargs):
    """安全文件操作包装器"""
    try:
        return operation_func(*args, **kwargs)
    except PermissionError as e:
        raise PermissionError(f"Permission denied: {e}")
    except OSError as e:
        raise OSError(f"File operation failed: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error during file operation: {e}")


def format_table(headers: List[str], rows: List[List[str]], min_width: int = 10) -> str:
    """格式化表格显示"""
    if not rows:
        return ""

    col_widths = [max(len(str(header)), min_width) for header in headers]

    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    header_line = " | ".join(
        header.ljust(col_widths[i]) for i, header in enumerate(headers)
    )
    separator_line = "-+-".join("-" * width for width in col_widths)

    lines = [header_line, separator_line]

    for row in rows:
        formatted_row = []
        for i, cell in enumerate(row):
            if i < len(col_widths):
                formatted_row.append(str(cell).ljust(col_widths[i]))
        lines.append(" | ".join(formatted_row))

    return "\n".join(lines)


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """查找项目根目录（包含.git或pyproject.toml等标记文件）"""
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    while current != current.parent:
        for marker in [".git", "pyproject.toml", "setup.py", "requirements.txt"]:
            if (current / marker).exists():
                return current
        current = current.parent

    return None


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """截断字符串到指定长度"""
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def parse_key_value_pairs(pairs: List[str]) -> Dict[str, str]:
    """解析KEY=VALUE格式的字符串列表"""
    result = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid format '{pair}'. Expected KEY=VALUE")

        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            raise ValueError("Key cannot be empty")

        result[key] = value

    return result


def colorize(text: str, color: str) -> str:
    """为文本添加颜色（仅在支持的终端中）"""
    if not sys.stdout.isatty():
        return text

    colors = {
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "white": "\033[37m",
        "reset": "\033[0m",
    }

    if color.lower() in colors:
        return f"{colors[color.lower()]}{text}{colors['reset']}"

    return text


def success_message(text: str) -> str:
    """成功消息格式化"""
    return colorize(f"✓ {text}", "green")


def error_message(text: str) -> str:
    """错误消息格式化"""
    return colorize(f"✗ {text}", "red")


def warning_message(text: str) -> str:
    """警告消息格式化"""
    return colorize(f"⚠ {text}", "yellow")


def info_message(text: str) -> str:
    """信息消息格式化"""
    return colorize(f"ℹ {text}", "blue")


def validate_environment_variable_name(name: str) -> bool:
    """验证环境变量名称是否有效"""
    if not name:
        return False

    return re.match(r"^[A-Z][A-Z0-9_]*$", name) is not None


def clean_environment_variable_value(value: str) -> str:
    """清理环境变量值"""
    value = value.strip()

    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    elif value.startswith("'") and value.endswith("'"):
        value = value[1:-1]

    return value


def get_file_permissions(file_path: Path) -> str:
    """获取文件权限字符串表示"""
    try:
        stat_info = file_path.stat()
        return oct(stat_info.st_mode)[-3:]
    except Exception:
        return "unknown"


def create_backup_filename(original_path: Path) -> Path:
    """创建备份文件名"""
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return original_path.with_suffix(f".{timestamp}.bak")


def is_writable_directory(path: Path) -> bool:
    """检查目录是否可写"""
    try:
        if not path.exists():
            return False

        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()
        return True
    except Exception:
        return False


def human_readable_size(size_bytes: int) -> str:
    """将字节数转换为人类可读的大小"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"
