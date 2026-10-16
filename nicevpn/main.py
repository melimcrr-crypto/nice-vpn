#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""نقطه ورود — GUI پیش‌فرض، با --cli حالت headless"""
import sys


def main():
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        from .cli import main as cli_main
        cli_main()
        return
    from .gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
