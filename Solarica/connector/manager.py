"""Solarica Connector Manager — Windows desktop control window."""

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
import urllib.request
import urllib.error
import json

BASE_DIR     = Path(__file__).parent
PYTHON_DIR   = BASE_DIR / "python"
DOTNET_DIR   = BASE_DIR / "dotnet" / "SolaricaConnector"
SOFTWARE_DIR = BASE_DIR.parent / "Software"
FTDI_SETUP   = SOFTWARE_DIR / "CDM_recent_driver_Setup.exe"
CONNECTOR_URL = "http://localhost:8765"

_PVPM_DIRS = [
    Path.home() / "Documents" / "PVPMdisp",
    Path.home() / "Documents" / "PVPMdisp" / "Samples",
    Path.home() / "Documents" / "PVPM_Export",
]

# ── Colours ───────────────────────────────────────────────────────────────────
BG        = "#f0f9ff"
CARD      = "#ffffff"
BORDER    = "#bae6fd"
GREEN     = "#16a34a"
GREEN_LT  = "#dcfce7"
RED       = "#dc2626"
RED_LT    = "#fee2e2"
YELLOW    = "#b45309"
YELLOW_LT = "#fef3c7"
BLUE      = "#1d4ed8"
BLUE_LT   = "#dbeafe"
MUTED     = "#64748b"
PRIMARY   = "#0ea5e9"
DARK      = "#0f172a"


def _read_pvpmdisp_ini() -> dict:
    ini_path = (
        Path.home() / "AppData" / "Roaming" / "PV-Engineering" / "PVPMdisp" / "PVPMdisp.INI"
    )
    result: dict = {}
    if not ini_path.exists():
        return result
    try:
        import configparser
        cfg = configparser.RawConfigParser()
        cfg.read(str(ini_path), encoding="latin-1")
        for section in cfg.sections():
            for key, val in cfg.items(section):
                result[key.upper()] = val.strip()
    except Exception:
        pass
    return result


def _find_pvpm_folder() -> Path | None:
    # Prefer EXPDIR from PVPMdisp.INI — that's where new exports land
    ini = _read_pvpmdisp_ini()
    for key in ("EXPDIR", "LASTDIR"):
        val = ini.get(key)
        if val:
            p = Path(val.rstrip("\\/"))
            if p.exists():
                return p
    for d in _PVPM_DIRS:
        if d.exists():
            return d
    return None


def _check_ftdi_installed() -> bool:
    try:
        import serial.tools.list_ports  # type: ignore[import]
        for p in serial.tools.list_ports.comports():
            desc = ((p.description or "") + " " + (p.manufacturer or "")).lower()
            if "ftdi" in desc or "usb serial" in desc:
                return True
    except Exception:
        pass
    try:
        out = subprocess.check_output(
            ["pnputil", "/enum-drivers"], text=True,
            stderr=subprocess.DEVNULL, timeout=5,
        )
        if "ftdi" in out.lower() or "cdm" in out.lower():
            return True
    except Exception:
        pass
    return False


def _list_pvpm_ports() -> list[tuple[str, str]]:
    """Return [(port, description)] for FTDI/PVPM COM ports."""
    try:
        import serial.tools.list_ports  # type: ignore[import]
        result = []
        for p in serial.tools.list_ports.comports():
            mfr  = (p.manufacturer or "").lower()
            desc = (p.description or "")
            if "ftdi" in mfr or "usb serial" in desc.lower():
                result.append((p.device, desc))
        return result
    except Exception:
        return []


def _api(path: str, method: str = "GET", body: dict | None = None) -> dict | None:
    try:
        data = json.dumps(body).encode() if body else None
        req  = urllib.request.Request(
            f"{CONNECTOR_URL}{path}",
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read())
    except Exception:
        return None


class ConnectorManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Solarica Connector Manager")
        self.geometry("460x540")
        self.resizable(False, False)
        self.configure(bg=BG)

        self._proc: subprocess.Popen | None = None
        self._polling   = True
        self._reading   = False          # serial capture in progress
        self._pvpm_folder = _find_pvpm_folder()

        self._build_ui()
        self._start_poll()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = dict(padx=18)

        # ── Title bar ────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=PRIMARY, height=48)
        top.pack(fill="x")
        top.pack_propagate(False)
        tk.Label(top, text="☀  Solarica Connector", bg=PRIMARY, fg="#fff",
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=14, pady=12)

        # ── Service status card ───────────────────────────────────────────────
        card = tk.Frame(self, bg=CARD, relief="flat", bd=0,
                        highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x", **pad, pady=(14, 0))

        r1 = tk.Frame(card, bg=CARD)
        r1.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(r1, text="Status", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        self._status_badge = tk.Label(r1, text="Checking…", bg="#e5e7eb", fg=DARK,
                                      font=("Segoe UI", 9, "bold"), padx=10, pady=2)
        self._status_badge.pack(side="left", padx=(8, 0))
        self._runtime_lbl = tk.Label(r1, text="", bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self._runtime_lbl.pack(side="left", padx=(10, 0))

        r2 = tk.Frame(card, bg=CARD)
        r2.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(r2, text="Port", bg=CARD, fg=MUTED, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(r2, text="localhost:8765", bg=CARD, fg=DARK,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(8, 0))

        # ── USB driver + folder card ──────────────────────────────────────────
        drv_card = tk.Frame(self, bg=CARD, relief="flat", bd=0,
                            highlightbackground=BORDER, highlightthickness=1)
        drv_card.pack(fill="x", **pad, pady=(8, 0))

        drv_row = tk.Frame(drv_card, bg=CARD)
        drv_row.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(drv_row, text="USB Driver", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self._drv_badge = tk.Label(drv_row, text="Checking…", bg="#e5e7eb", fg=DARK,
                                   font=("Segoe UI", 9, "bold"), padx=10, pady=2)
        self._drv_badge.pack(side="left", padx=(8, 0))
        self._install_btn = tk.Button(
            drv_row, text="Install Driver", command=self._install_driver,
            bg=YELLOW, fg="#fff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=10, pady=2, cursor="hand2",
            activebackground="#92400e", activeforeground="#fff", bd=0,
        )
        self._install_btn.pack(side="left", padx=(10, 0))
        self._install_btn.pack_forget()

        folder_row = tk.Frame(drv_card, bg=CARD)
        folder_row.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(folder_row, text="Data folder", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        folder_text  = str(self._pvpm_folder) if self._pvpm_folder else "Not found"
        folder_color = DARK if self._pvpm_folder else RED
        tk.Label(folder_row, text=folder_text, bg=CARD, fg=folder_color,
                 font=("Segoe UI", 8), wraplength=280, justify="left"
                 ).pack(side="left", padx=(8, 0))

        # ── Direct device access card ─────────────────────────────────────────
        dev_card = tk.Frame(self, bg=CARD, relief="flat", bd=0,
                            highlightbackground=BORDER, highlightthickness=1)
        dev_card.pack(fill="x", **pad, pady=(8, 0))

        dev_title = tk.Frame(dev_card, bg=CARD)
        dev_title.pack(fill="x", padx=14, pady=(10, 6))
        tk.Label(dev_title, text="PVPM Device", bg=CARD, fg=DARK,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        # Port row (populated dynamically)
        self._dev_port_frame = tk.Frame(dev_card, bg=CARD)
        self._dev_port_frame.pack(fill="x", padx=14, pady=(0, 4))
        self._dev_port_lbl = tk.Label(self._dev_port_frame, text="Scanning…",
                                      bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self._dev_port_lbl.pack(side="left")

        # Device status badge
        dev_status_row = tk.Frame(dev_card, bg=CARD)
        dev_status_row.pack(fill="x", padx=14, pady=(0, 4))
        tk.Label(dev_status_row, text="Connected", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self._dev_conn_badge = tk.Label(dev_status_row, text="—", bg="#e5e7eb", fg=DARK,
                                        font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        self._dev_conn_badge.pack(side="left", padx=(8, 0))

        # Action buttons row
        dev_btn_row = tk.Frame(dev_card, bg=CARD)
        dev_btn_row.pack(fill="x", padx=14, pady=(4, 10))

        self._connect_btn = tk.Button(
            dev_btn_row, text="⚡  Connect to Device",
            command=self._connect_device,
            bg=BLUE, fg="#fff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#1e3a8a", activeforeground="#fff", bd=0,
        )
        self._connect_btn.pack(side="left")

        self._read_btn = tk.Button(
            dev_btn_row, text="⬇  Read from Device",
            command=self._read_device,
            bg="#0ea5e9", fg="#fff", font=("Segoe UI", 9, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#0284c7", activeforeground="#fff", bd=0,
            state="disabled",
        )
        self._read_btn.pack(side="left", padx=(8, 0))

        self._disconnect_dev_btn = tk.Button(
            dev_btn_row, text="Disconnect",
            command=self._disconnect_device,
            bg="#64748b", fg="#fff", font=("Segoe UI", 9),
            relief="flat", padx=10, pady=6, cursor="hand2",
            activebackground="#475569", activeforeground="#fff", bd=0,
            state="disabled",
        )
        self._disconnect_dev_btn.pack(side="left", padx=(8, 0))

        # ── Version + service buttons ─────────────────────────────────────────
        ver_frame = tk.Frame(self, bg=BG)
        ver_frame.pack(fill="x", **pad, pady=(12, 0))
        tk.Label(ver_frame, text="Version", bg=BG, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="left")
        self._version_var = tk.StringVar(value="python")
        for val, label in [("python", "Python"), ("dotnet", ".NET")]:
            tk.Radiobutton(
                ver_frame, text=label, variable=self._version_var, value=val,
                bg=BG, fg=DARK, selectcolor=BG, activebackground=BG,
                font=("Segoe UI", 10), cursor="hand2",
            ).pack(side="left", padx=(12, 0))

        pvpm_exe = Path(r"C:\Program Files (x86)\PVPMdisp\PVPMdisp.exe")
        if pvpm_exe.exists():
            pvpm_row = tk.Frame(self, bg=BG)
            pvpm_row.pack(fill="x", **pad, pady=(8, 0))
            tk.Button(
                pvpm_row, text="📂  Open PVPM Software", command=self._launch_pvpm,
                bg="#334155", fg="#fff", font=("Segoe UI", 9, "bold"),
                relief="flat", padx=14, pady=5, cursor="hand2",
                activebackground="#1e293b", activeforeground="#fff", bd=0,
            ).pack(side="left")
            tk.Label(pvpm_row, text="→ Transfer Mode", bg=BG, fg=MUTED,
                     font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack(fill="x", **pad, pady=(10, 0))

        self._start_btn = tk.Button(
            btn_frame, text="▶  Start", command=self._start,
            bg=GREEN, fg="#fff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=8, cursor="hand2",
            activebackground="#15803d", activeforeground="#fff", bd=0,
        )
        self._start_btn.pack(side="left")

        self._stop_btn = tk.Button(
            btn_frame, text="■  Stop", command=self._stop,
            bg=RED, fg="#fff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=8, cursor="hand2",
            activebackground="#b91c1c", activeforeground="#fff", bd=0, state="disabled",
        )
        self._stop_btn.pack(side="left", padx=(10, 0))

        self._restart_btn = tk.Button(
            btn_frame, text="↺  Restart", command=self._restart,
            bg=PRIMARY, fg="#fff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=20, pady=8, cursor="hand2",
            activebackground="#0284c7", activeforeground="#fff", bd=0, state="disabled",
        )
        self._restart_btn.pack(side="left", padx=(10, 0))

        self._log = tk.Label(self, text="", bg=BG, fg=MUTED,
                             font=("Segoe UI", 8), wraplength=420)
        self._log.pack(fill="x", **pad, pady=(10, 8))

        # Kick off driver + port scan
        threading.Thread(target=self._refresh_driver_status, daemon=True).start()
        threading.Thread(target=self._scan_device_ports, daemon=True).start()

    # ── Driver badge ──────────────────────────────────────────────────────────

    def _refresh_driver_status(self):
        installed = _check_ftdi_installed()
        self.after(0, self._update_driver_badge, installed)

    def _update_driver_badge(self, installed: bool):
        if installed:
            self._drv_badge.config(text="Installed", bg=GREEN_LT, fg=GREEN)
            self._install_btn.pack_forget()
        else:
            self._drv_badge.config(text="Not installed", bg=YELLOW_LT, fg=YELLOW)
            if FTDI_SETUP.exists():
                self._install_btn.pack(side="left", padx=(10, 0))

    def _install_driver(self):
        if not FTDI_SETUP.exists():
            return
        self._log.config(text="Launching FTDI driver installer…")
        self._install_btn.config(state="disabled")
        def run():
            subprocess.Popen([str(FTDI_SETUP)], shell=False)
            time.sleep(8)
            installed = _check_ftdi_installed()
            self.after(0, self._update_driver_badge, installed)
            if installed:
                self.after(0, self._log.config, {"text": "FTDI driver installed."})
            self.after(0, self._install_btn.config, {"state": "normal"})
        threading.Thread(target=run, daemon=True).start()

    # ── Device port scan ──────────────────────────────────────────────────────

    def _scan_device_ports(self):
        ports = _list_pvpm_ports()
        self.after(0, self._update_device_ports, ports)

    def _update_device_ports(self, ports: list[tuple[str, str]]):
        if ports:
            names = "  ".join(f"{p}  ({d})" for p, d in ports)
            self._dev_port_lbl.config(text=names, fg=DARK)
            self._pvpm_port = ports[0][0]  # default to first FTDI port
        else:
            self._dev_port_lbl.config(text="No PVPM device detected on USB", fg=MUTED)
            self._pvpm_port = None

    # ── Device connect / read / disconnect ────────────────────────────────────

    def _connect_device(self):
        port = getattr(self, "_pvpm_port", None)
        if not port:
            self._log.config(text="No PVPM device found. Check the USB cable.")
            return
        self._log.config(text=f"Connecting to {port}…")
        self._connect_btn.config(state="disabled")

        def run():
            result = _api("/api/device/connect", "POST", {"port": port})
            if result and result.get("connected"):
                self.after(0, self._on_device_connected, port)
            else:
                err = (result or {}).get("lastError", "Connection failed")
                self.after(0, self._log.config, {"text": err})
                self.after(0, self._connect_btn.config, {"state": "normal"})

        threading.Thread(target=run, daemon=True).start()

    def _on_device_connected(self, port: str):
        self._dev_conn_badge.config(text=f"Yes  ({port})", bg=GREEN_LT, fg=GREEN)
        self._connect_btn.config(state="disabled")
        self._read_btn.config(state="normal")
        self._disconnect_dev_btn.config(state="normal")
        self._log.config(text=f"Connected to {port}. Press Transfer on device, then click Read.")

    def _read_device(self):
        if self._reading:
            return
        self._reading = True
        self._read_btn.config(state="disabled", text="⏳  Waiting for device…")
        self._log.config(text="Press the Transfer button on the PVPM device now…")

        def run():
            result = _api("/api/import/start", "POST")
            imported = (result or {}).get("imported", 0)
            if imported:
                msg = f"✓ Captured {imported} measurement{'s' if imported != 1 else ''} from device."
            else:
                err = (result or {}).get("detail", "No data received.")
                msg = f"No data. {err}  Make sure device is in Transfer Mode."
            self._reading = False
            self.after(0, self._read_btn.config, {"state": "normal", "text": "⬇  Read from Device"})
            self.after(0, self._log.config, {"text": msg})

        threading.Thread(target=run, daemon=True).start()

    def _disconnect_device(self):
        _api("/api/device/disconnect", "POST")
        self._dev_conn_badge.config(text="—", bg="#e5e7eb", fg=DARK)
        self._connect_btn.config(state="normal")
        self._read_btn.config(state="disabled")
        self._disconnect_dev_btn.config(state="disabled")
        self._log.config(text="Device disconnected.")

    # ── Health polling ────────────────────────────────────────────────────────

    def _check_health(self) -> dict | None:
        try:
            with urllib.request.urlopen(f"{CONNECTOR_URL}/health", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            return None

    def _start_poll(self):
        def loop():
            while self._polling:
                health = self._check_health()
                self.after(0, self._update_status, health)
                time.sleep(3)
        threading.Thread(target=loop, daemon=True).start()

    def _update_status(self, health: dict | None):
        if health and health.get("ok"):
            runtime = health.get("runtime", "?")
            version = health.get("version", "?")
            self._status_badge.config(text="Online", bg=GREEN_LT, fg=GREEN)
            self._runtime_lbl.config(text=f"{runtime}  ·  v{version}")
            self._start_btn.config(state="disabled")
            self._stop_btn.config(state="normal")
            self._restart_btn.config(state="normal")
            if runtime in ("python", "dotnet"):
                self._version_var.set(runtime)
        else:
            self._status_badge.config(text="Offline", bg=RED_LT, fg=RED)
            self._runtime_lbl.config(text="")
            self._start_btn.config(state="normal")
            self._stop_btn.config(state="disabled")
            self._restart_btn.config(state="disabled")

    # ── Service start / stop / restart ────────────────────────────────────────

    def _kill_proc(self):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        try:
            result = subprocess.check_output(
                'netstat -ano | findstr :8765', shell=True, text=True)
            for line in result.strip().splitlines():
                parts = line.split()
                if parts and parts[-1].isdigit():
                    subprocess.call(f"taskkill /PID {parts[-1]} /F", shell=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _launch(self, version: str):
        self._kill_proc()
        time.sleep(0.5)
        watch_folder = str(self._pvpm_folder) if self._pvpm_folder else str(PYTHON_DIR / "import_watch")
        if version == "python":
            self._proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "main:app",
                 "--host", "127.0.0.1", "--port", "8765"],
                cwd=str(PYTHON_DIR),
                env={**os.environ, "PVPM_DRIVER": "serial", "WATCH_FOLDER": watch_folder},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        else:
            self._proc = subprocess.Popen(
                ["dotnet", "run", "--project", str(DOTNET_DIR)],
                cwd=str(DOTNET_DIR),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )

    def _start(self):
        version = self._version_var.get()
        self._log.config(text=f"Starting {version} connector…")
        self._start_btn.config(state="disabled")
        def run():
            self._launch(version)
            for _ in range(20):
                time.sleep(1)
                if self._check_health():
                    self.after(0, self._log.config, {"text": f"{version} connector started."})
                    return
            self.after(0, self._log.config, {"text": "Connector did not respond in time."})
        threading.Thread(target=run, daemon=True).start()

    def _stop(self):
        self._log.config(text="Stopping connector…")
        def run():
            self._kill_proc()
            time.sleep(1)
            self.after(0, self._log.config, {"text": "Connector stopped."})
        threading.Thread(target=run, daemon=True).start()

    def _restart(self):
        version = self._version_var.get()
        self._log.config(text=f"Restarting as {version}…")
        def run():
            self._launch(version)
            for _ in range(20):
                time.sleep(1)
                if self._check_health():
                    self.after(0, self._log.config, {"text": f"Restarted as {version}."})
                    return
            self.after(0, self._log.config, {"text": "Connector did not respond in time."})
        threading.Thread(target=run, daemon=True).start()

    def _launch_pvpm(self):
        pvpm_exe = Path(r"C:\Program Files (x86)\PVPMdisp\PVPMdisp.exe")
        if pvpm_exe.exists():
            subprocess.Popen([str(pvpm_exe)], shell=False)
            self._log.config(text="PVPMdisp launched — use Transfer Mode to copy measurements.")
        else:
            self._log.config(text="PVPMdisp not found.")

    def _on_close(self):
        self._polling = False
        self.destroy()


if __name__ == "__main__":
    app = ConnectorManager()
    app.mainloop()
