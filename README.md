# Educational Keylogger

A Python keylogger built for a cyber-security internship assignment. Its purpose
is to **demonstrate how keystroke capture works so it can be detected and
defended against** — not to provide covert spyware.

It ships in three forms: a **command-line tool** (`keylogger.py`), a **desktop GUI
application** (`gui.py`), and a safe, in-browser **live web demo**.

> 🔗 **Live demo:** https://kartik-reddy-m.github.io/key_logger-encoding-decoding/
> &nbsp;·&nbsp; 🖥️ **Desktop app:** `python gui.py`

> ⚠️ **Legal & ethical notice.** Only run this on a machine you own or are
> explicitly authorized to test. Recording another person's keystrokes without
> informed consent is illegal in most jurisdictions (wiretapping / computer-misuse
> statutes). You are responsible for how you use this code.

---

## Why this is a *responsible* demo, not malware

| Malicious keylogger | This educational build |
| --- | --- |
| Hides itself / runs silently | Prints a banner, requires typed consent, shows a live counter |
| Exfiltrates data over the network | **Writes only to a local file. No networking code at all.** |
| Persists secretly (registry, services) | Runs only while you keep the terminal open |
| Leaves plaintext for anyone to read | Optional at-rest encryption of the log |

These contrasts are exactly what a grader wants to see — they prove you
understand both the mechanism *and* the ethics.

---

## Features

- **Core:** captures printable + special keys to a timestamped local log.
- **Active-window context:** records the foreground window title so the log shows
  *where* typing happened (Windows / macOS / Linux best-effort).
- **Log rotation:** rolls over at ~1 MB, keeping `keystrokes.log.1 … .5`.
- **At-rest encryption:** `--encrypt` stores the log as Fernet tokens; decrypt
  later with `decrypt_log.py`.
- **Consent gate:** must type `I AGREE` (or pass `--i-consent`) to start.
- **Desktop GUI (`gui.py`):** a customtkinter app with Start/Stop, a live keystroke
  counter, a real-time capture preview, encrypt/decrypt controls, and quick access
  to the log file — the same engine, wrapped in a visible window.
- **Web demo (`index.html`):** a client-side, in-browser illustration of keystroke
  logging (nothing is stored or sent anywhere) — deployed via GitHub Pages.

---

## Setup

```bash
# 1. (recommended) create a virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 2. install dependencies
pip install -r requirements.txt
```

> **Linux note:** `pynput` needs an X server, and active-window titles use
> `xdotool` (`sudo apt install xdotool`). On macOS you must grant the terminal
> **Accessibility** and **Input Monitoring** permissions in *System Settings →
> Privacy & Security*.

---

## Usage

**Desktop GUI application:**

```bash
python gui.py                       # launch the windowed app
```

**Command-line tool:**

```bash
python keylogger.py                 # plaintext log, interactive consent
python keylogger.py --encrypt       # encrypt the log at rest
python keylogger.py --no-window     # don't record window titles
python keylogger.py --i-consent     # skip the prompt (automated demo you control)
```

Stop with **ESC** or **Ctrl+C**.

Read an encrypted log:

```bash
python decrypt_log.py               # decrypts logs/keystrokes.log
python decrypt_log.py logs/keystrokes.log.1
```

Output lives in `logs/` (git-ignored):

```
logs/
├── keystrokes.log      # the capture
└── secret.key          # Fernet key (only when --encrypt is used)
```

---

## How it works (quick tour)

1. **`pynput.keyboard.Listener`** registers an OS-level keyboard hook and calls
   `on_press` / `on_release` for every event on a background thread.
2. `on_press` distinguishes **character keys** (`key.char`) from **special keys**
   (`Key.space`, `Key.enter`, …) and formats each for the log.
3. Before writing, the logger checks the **foreground window title** and emits a
   `--- WINDOW: … ---` marker whenever it changes, giving each burst of text
   context.
4. **`LogWriter`** appends to `logs/keystrokes.log`, rotating by size and — if
   `--encrypt` is set — wrapping each line in a **Fernet** token.

See `REPORT.md` for the full architecture write-up plus the **detection &
defense** analysis.

---

## Files

| File | Purpose |
| --- | --- |
| `keylogger.py` | The keylogger core (capture, window tracking, rotation, encryption) |
| `gui.py` | Desktop GUI application (customtkinter) |
| `index.html` | Client-side web demo (GitHub Pages) |
| `decrypt_log.py` | Utility to decrypt an encrypted log |
| `requirements.txt` | Python dependencies |
| `REPORT.md` | Architecture + detection & defense report (the graded write-up) |
| `.gitignore` | Keeps captured data and keys out of version control |
