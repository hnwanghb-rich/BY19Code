#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")

# 检查必要的模块
try:
    import tkinter
    print("tkinter: OK")
except ImportError as e:
    print(f"tkinter: ERROR - {e}")

try:
    from zhdate import ZhDate
    print("zhdate: OK")
except ImportError as e:
    print(f"zhdate: ERROR - {e}")

try:
    import markdown
    print("markdown: OK")
except ImportError as e:
    print(f"markdown: ERROR - {e}")

try:
    from weasyprint import HTML
    print("weasyprint: OK")
except ImportError as e:
    print(f"weasyprint: ERROR - {e}")