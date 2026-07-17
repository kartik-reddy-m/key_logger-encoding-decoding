"""
Decrypt an encrypted keystroke log produced by keylogger.py --encrypt.

Usage:
    python decrypt_log.py                       # decrypts logs/keystrokes.log
    python decrypt_log.py logs/keystrokes.log.1 # decrypt a rotated log
"""

import sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:
    sys.exit("This tool needs 'cryptography'.  Run: pip install -r requirements.txt")

LOG_DIR = Path(__file__).resolve().parent / "logs"
KEY_FILE = LOG_DIR / "secret.key"
DEFAULT_LOG = LOG_DIR / "keystrokes.log"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG
    if not KEY_FILE.exists():
        sys.exit(f"Key file not found: {KEY_FILE}")
    if not target.exists():
        sys.exit(f"Log file not found: {target}")

    fernet = Fernet(KEY_FILE.read_bytes())
    print(f"--- Decrypted contents of {target} ---\n")
    with open(target, "rb") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            try:
                sys.stdout.write(fernet.decrypt(raw).decode("utf-8"))
            except InvalidToken:
                print("\n[!] A line could not be decrypted (wrong key or corrupt).")
    print("\n\n--- end ---")


if __name__ == "__main__":
    main()
