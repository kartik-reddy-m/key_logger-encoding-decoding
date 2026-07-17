# Keyloggers: Architecture, Implementation, and Defense

**Cyber-Security Internship Assignment**

---

## 1. Introduction

A **keylogger** (keystroke logger) records the keys a user presses. The
technology is *dual-use*: it powers legitimate tools (parental controls with
disclosure, accessibility software, QA automation, authorized red-team
engagements) and, when deployed covertly, it is a core component of spyware used
to steal passwords and financial data.

This project implements a **transparent, local-only** keylogger in Python to
learn the mechanism first-hand, then analyzes **how such tools are detected and
defended against** — the perspective a defensive security team actually needs.

---

## 2. How keyloggers capture input

Keystrokes travel through several layers between the physical key and the
application. A keylogger can tap in at any of them:

| Type | Where it hooks | Notes |
| --- | --- | --- |
| **Hardware** | Inline USB device or modified keyboard | Invisible to software; stores keys in onboard memory |
| **Kernel / driver** | A driver in the input stack | Stealthy, needs admin/root, hardest to detect |
| **API / user-mode hook** | OS input APIs (`SetWindowsHookEx`, macOS event taps, X11/`evdev`) | Most common; what this project uses via `pynput` |
| **Form-grabber / browser** | Inside the browser or a malicious extension | Captures web-form data directly |
| **Acoustic / side-channel** | Microphone, EM emissions | Research-grade, infers keys indirectly |

This project sits in the **user-mode API-hook** category — the most common and
the most instructive.

---

## 3. Architecture of this implementation

```
                 ┌──────────────────────────────────────────┐
                 │                keylogger.py                │
                 │                                            │
  Physical  ──►  │  pynput.keyboard.Listener  (OS hook)       │
  keypress       │            │                               │
                 │            ▼                               │
                 │        on_press(key)                       │
                 │         │        │                         │
                 │         ▼        ▼                         │
                 │  get_active_    format key                 │
                 │  window_title() (char / special)           │
                 │         │        │                         │
                 │         └────┬───┘                         │
                 │              ▼                             │
                 │         LogWriter.write()                  │
                 │          │         │                       │
                 │   rotate by size   optional Fernet         │
                 │          │         encryption              │
                 │          ▼         ▼                       │
                 │        logs/keystrokes.log                 │
                 └──────────────────────────────────────────┘
```

### Key components

- **`keyboard.Listener`** — registers a global keyboard hook and dispatches every
  key event to callbacks on a background thread.
- **`Keylogger.on_press`** — classifies each key. Printable keys expose a
  `.char`; special keys (space, enter, shift, backspace, …) do not, and are
  written as readable tokens like `[shift]`.
- **`get_active_window_title`** — queries the foreground window (Win32
  `GetForegroundWindow`/`GetWindowTextW`, `osascript` on macOS, `xdotool` on
  Linux) so the log records *which application* received the typing.
- **`LogWriter`** — appends to disk, **rotates** the file at ~1 MB, and can
  **encrypt** each line with a symmetric **Fernet** key stored in `secret.key`.
- **Consent gate** — the program refuses to run until the operator types
  `I AGREE`, and it prints a live keystroke counter so operation is obvious.

### Deliberate limitations (ethical guardrails)

- **No networking** — there is no code to send data anywhere. A real threat
  would exfiltrate over HTTP/DNS/email; omitting it keeps this safe to demo.
- **No persistence** — it does not install itself into the registry, a service,
  a launch agent, or a scheduled task. It runs only while the terminal is open.
- **No stealth** — no process-name spoofing, no hiding from Task Manager.

---

## 4. Detection

Understanding capture makes detection concrete. Defenders look for the
behavioral and static traces a keylogger leaves behind.

### 4.1 Behavioral indicators
- **A process installing a global keyboard hook.** On Windows, EDR tools flag
  `SetWindowsHookEx(WH_KEYBOARD_LL, …)`; macOS flags apps requesting
  *Input Monitoring* / *Accessibility*.
- **Unexpected outbound traffic** — periodic small POSTs, odd DNS queries, or
  email from a non-mail process often reveal the *exfiltration* half of real
  spyware even when the capture itself is quiet.
- **A process writing steadily to an obscure file** in `%APPDATA%`, `/tmp`, or a
  hidden directory.
- **Persistence artifacts** — new `Run` registry keys, scheduled tasks, services,
  launch agents, or startup-folder entries.

### 4.2 Static / host indicators
- **Antivirus / EDR signatures** for known keylogger families and, increasingly,
  behavioral ML detections.
- **Autoruns / Task Manager / `tasklist`** review for unknown auto-starting
  processes.
- **Integrity monitoring** of startup locations and driver lists (a rogue driver
  hints at a kernel-mode logger).
- **Physical inspection** — check for an inline USB device between keyboard and
  port; hardware loggers are undetectable by software.

### 4.3 Network indicators
- Beaconing patterns, data sent to unfamiliar domains/IPs, or DNS tunneling —
  visible in a firewall, proxy, or IDS such as Suricata/Zeek.

---

## 5. Defense and mitigation

Layered controls, because no single measure is sufficient:

| Layer | Control |
| --- | --- |
| **Reduce impact** | **Multi-factor authentication** — a stolen password alone becomes far less useful. |
| **Avoid typing secrets** | **Password managers** autofill credentials, so they are never keyed in. |
| **Endpoint** | Reputable, updated **AV/EDR**; application allow-listing; least-privilege accounts so malware can't install drivers/services. |
| **OS hygiene** | Patch promptly; review autoruns and installed drivers; enable Windows tamper protection / macOS SIP. |
| **Network** | Egress filtering and monitoring to catch exfiltration even if capture is missed. |
| **User awareness** | Don't run untrusted executables; be wary of phishing that delivers loggers. |
| **High-risk sessions** | On-screen keyboards, keystroke-encryption tools, or a clean/dedicated device for sensitive logins. |
| **Physical** | Inspect shared/public machines for inline hardware loggers; lock down USB ports. |

**Why MFA and password managers top the list:** they attack the *value* of the
stolen data rather than trying to win an endless cat-and-mouse over detection.

---

## 6. Legal and ethical considerations

- Installing a keylogger on a device you do not own, or without informed consent,
  typically violates **wiretapping** and **computer-misuse** laws (e.g. the U.S.
  CFAA and ECPA, the UK Computer Misuse Act, India's IT Act §43/66).
- Even legitimate monitoring (employers, parents) is usually bound by
  **disclosure and proportionality** requirements that vary by jurisdiction.
- This project mitigates risk by being **consent-gated, non-stealth, local-only,
  and non-persistent** — properties a real attacker would remove and a defender
  should therefore treat as red flags when absent.

---

## 7. How to demonstrate (for the assessor)

1. `pip install -r requirements.txt`
2. Run `python keylogger.py`, type `I AGREE`.
3. Type into Notepad / a browser; watch the live counter, then press **ESC**.
4. Open `logs/keystrokes.log` and show the `--- WINDOW: … ---` context markers.
5. Re-run with `python keylogger.py --encrypt`, capture again, show the log is
   now unreadable ciphertext, then reveal it with `python decrypt_log.py`.
6. Walk through §4–§5 to explain how you would *detect and stop* this on a real
   network.

---

## 8. Conclusion

Building a keylogger clarifies that the capture mechanism is simple — a single
OS hook — while the security story lives in **exfiltration, persistence, stealth,
detection, and layered defense**. By keeping this implementation transparent and
local, the project demonstrates the mechanism responsibly and centers the
defensive lessons that matter to a security team: assume keystrokes *can* be
captured, and design controls (MFA, password managers, EDR, egress monitoring)
so that it doesn't matter when they are.

---

### References for further reading
- MITRE ATT&CK — *Input Capture: Keylogging* (T1056.001)
- OWASP — guidance on credential theft and MFA
- Microsoft Docs — `SetWindowsHookEx`, low-level keyboard hooks
- `pynput` documentation — keyboard monitoring API
