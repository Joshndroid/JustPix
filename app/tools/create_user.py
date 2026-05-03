from __future__ import annotations

import argparse
import json
from getpass import getpass

from app.auth.passwords import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a JustPix users.json entry.")
    parser.add_argument("username")
    parser.add_argument("--display-name", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--role", choices=["admin", "user"], default="user")
    parser.add_argument("--json", action="store_true", help="Print a full users.json document")
    args = parser.parse_args()

    password = args.password or getpass("Password: ")
    entry = {
        "username": args.username,
        "password_hash": hash_password(password),
        "display_name": args.display_name or args.username,
        "role": args.role,
        "disabled": False,
    }
    print(json.dumps({"users": [entry]} if args.json else entry, indent=2))


if __name__ == "__main__":
    main()
