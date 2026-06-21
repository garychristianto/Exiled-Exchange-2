#!/usr/bin/env python3
"""Paste a PoE2 'Copy Item' text and get a readable analysis.

Usage:
    python craft.py < item.txt
    python craft.py item.txt
    pbpaste | python craft.py        # macOS
"""
import sys

from craftsim.item_parse import parse_item
from craftsim.present import present


def main() -> None:
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()
    if not text.strip():
        print("No item text provided. Paste a PoE2 'Copy Item' block.")
        return
    print(present(parse_item(text)))


if __name__ == "__main__":
    main()
