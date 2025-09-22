#!/usr/bin/env python3
"""
AISwitch - AI API环境切换工具

主入口文件，可以通过 python -m aiswitch 或直接运行 python main.py 来使用。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aiswitch.cli import main

if __name__ == "__main__":
    main()
