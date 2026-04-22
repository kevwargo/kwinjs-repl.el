#!/usr/bin/env python3

import json
import sys


def main():
    while True:
        print("KWin JS #> ", end="", flush=True)
        line = json.loads(sys.stdin.readline())
        print(f"resp {line}!", flush=True)

        if line in ("exit;", "quit;"):
            break


if __name__ == "__main__":
    main()
