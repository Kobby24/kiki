"""
Moolre mobile money name lookup (Ghana).

Setup:
    pip install requests

    export MOOLRE_API_USER="your_moolre_username"
    export MOOLRE_API_KEY="your_api_key"
    export MOOLRE_ACCOUNT_NUMBER="your_moolre_account_number"

Usage:
    python moolre_name_lookup.py 0241234567
    python moolre_name_lookup.py 0201234567 --channel telecel
"""

import argparse
import os
import re
import sys

import requests

VALIDATE_URL = "https://api.moolre.com/open/transact/validate"

# Moolre channel IDs (from their Validate Name docs)
CHANNELS = {"mtn": "1", "telecel": "6", "at": "7"}

# Common Ghana prefixes (after the leading 0). Numbers can be ported between
# networks, so treat this as a best guess and allow an explicit override.
PREFIXES = {
    "mtn": ("24", "25", "53", "54", "55", "59"),
    "telecel": ("20", "50"),
    "at": ("26", "27", "56", "57"),
}


class MoolreError(Exception):
    """Raised for configuration problems or API/network failures."""


def normalize_phone(phone: str) -> str:
    """Return a local 10-digit Ghana number, e.g. 0241234567.

    Accepts '0241234567', '241234567', '233241234567' or '+233 24 123 4567'.
    """
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("233"):
        digits = digits[3:]
    if len(digits) == 9:
        digits = "0" + digits
    if not re.fullmatch(r"0\d{9}", digits):
        raise MoolreError(f"Invalid Ghana phone number: {phone!r}")
    return digits


def detect_network(local_number: str):
    """Guess the network from the prefix. Returns 'mtn', 'telecel', 'at' or None."""
    prefix = local_number[1:3]
    for network, prefixes in PREFIXES.items():
        if prefix in prefixes:
            return network
    return None


class MoolreClient:
    def __init__(self, api_user=None, api_key=None, account_number=None, timeout=15):
        self.api_user = api_user or os.getenv("MOOLRE_API_USER")
        self.api_key = api_key or os.getenv("MOOLRE_API_KEY")
        self.account_number = account_number or os.getenv("MOOLRE_ACCOUNT_NUMBER")
        self.timeout = timeout

        missing = [
            name
            for name, value in [
                ("MOOLRE_API_USER", self.api_user),
                ("MOOLRE_API_KEY", self.api_key),
                ("MOOLRE_ACCOUNT_NUMBER", self.account_number),
            ]
            if not value
        ]
        if missing:
            raise MoolreError(f"Missing credentials: {', '.join(missing)}")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-USER": self.api_user,
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            }
        )

    def get_name(self, phone: str, network: str = None):
        """Look up the registered name for a mobile money number.

        Returns the name as a string, or None if the number isn't found.
        Raises MoolreError on bad input, network errors or unexpected responses.
        """
        local = normalize_phone(phone)

        network = (network or detect_network(local) or "").lower()
        if network not in CHANNELS:
            raise MoolreError(
                f"Could not determine network for {local}. "
                f"Pass network= one of {list(CHANNELS)}."
            )

        payload = {
            "type": 1,
            "receiver": local,
            "channel": CHANNELS[network],
            "currency": "GHS",
            "accountnumber": self.account_number,
        }

        try:
            resp = self.session.post(VALIDATE_URL, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            raise MoolreError(f"Network error calling Moolre: {exc}") from exc

        try:
            body = resp.json()
        except ValueError:
            raise MoolreError(f"Non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}")

        if body.get("status") == 1:
            data = body.get("data")
            # Docs show a plain string; handle a {"name": ...} object too.
            if isinstance(data, dict):
                data = data.get("name")
            return data.strip() if isinstance(data, str) else None

        message = str(body.get("message", "")).lower()
        if "not found" in message:
            return None

        raise MoolreError(
            f"Moolre error (code={body.get('code')}): {body.get('message')}"
        )

    def get_name_any_network(self, phone: str):
        """Try the detected network first, then the others (handles ported numbers).

        Returns (name, network) or (None, None).
        """
        local = normalize_phone(phone)
        guess = detect_network(local)
        order = ([guess] if guess else []) + [n for n in CHANNELS if n != guess]

        for network in order:
            name = self.get_name(local, network=network)
            if name:
                return name, network
        return None, None


def main():
    parser = argparse.ArgumentParser(description="Moolre mobile money name lookup")
    parser.add_argument("phone", help="e.g. 0241234567 or 233241234567")
    parser.add_argument("--channel", choices=list(CHANNELS), help="Force a network")
    parser.add_argument(
        "--any", action="store_true", help="Try all networks if the first fails"
    )
    args = parser.parse_args()

    try:
        client = MoolreClient()
        if args.any:
            name, network = client.get_name_any_network(args.phone)
            if name:
                print(f"{name} ({network})")
                return
        else:
            name = client.get_name(args.phone, network=args.channel)
            if name:
                print(name)
                return
        print("No account found for that number.")
        sys.exit(1)
    except MoolreError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
