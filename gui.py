# -*- coding: utf-8 -*-
"""
gui.py — DailyPrintHaus 자동화 컨트롤 패널 (tkinter)

실행: python gui.py
exe: pyinstaller --onefile --noconsole gui.py
"""
import sys
import os
import threading
import subprocess
import json
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent
PYTHON   = sys.executable
QUEUE_FILE    = BASE_DIR / "publish_queue.json"
PROGRESS_FILE = BASE_DIR / "daily_progress.json"


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | list:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {} if path == PROGRESS_FILE else []


def _queue_summary() -> str:
    q = _load_json(QUEUE_FILE)
    if not q:
        return "큐: 비어 있음"
    done    = sum(1 for e in q if e.get("done"))
    pending = len(q) - done
    return f"큐: 대기 {pending}개 / 완료 {done}개"


def _progress_summary() -> str:
    p = _load_json(PROGRESS_FILE)
    published = len(p.get("published", []))
    total     = 1600
    pct       = published / total * 100
    return f"발행 현황: {published}/{total}개 ({pct:.1f}%)"


# ── 메인 앱 ──────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DailyPrintHaus — 자동화 컨트롤")
        self.geometry("760x600")
        self.resizable(True, True)
        self.configure(bg="#1e1e2e")
        self._running = False
        self._build_ui()
        self._refresh_status()

    # ── UI 구성 ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # 헤더
        hdr = tk.Frame(self, bg="#181825", pady=10)
        hdr.pack(fill="x")
        tk.Label(hdr, text="DailyPrintHaus", font=("Segoe UI", 18, "bold"),
                 bg="#181825", fg="#cdd6f4").pack(side="left", padx=16)
        tk.Label(hdr, text="Etsy 자동화 컨트롤",
                 font=("Segoe UI", 10), bg="#181825", fg="#6c7086").pack(side="left")

        # 상태바
        status_frame = tk.Frame(self, bg="#1e1e2e", pady=6)
        status_frame.pack(fill="x", padx=16)

        self.lbl_progress = tk.Label(status_frame, text="",
                                     font=("Segoe UI", 10), bg="#1e1e2e", fg="#a6e3a1")
        self.lbl_progress.pack(side="left")

        self.lbl_queue = tk.Label(status_frame, text="",
                                  font=("Segoe UI", 10), bg="#1e1e2e", fg="#89b4fa")
        self.lbl_queue.pack(side="left", padx=20)

        btn_refresh = tk.Button(status_frame, text="↺ 새로고침",
                                command=self._refresh_status,
                                bg="#313244", fg="#cdd6f4",
                                relief="flat", padx=8, cursor="hand2")
        btn_refresh.pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16)

        # 버튼 영역
        btn_frame = tk.Frame(self, bg="#1e1e2e", pady=10)
        btn_frame.pack(fill="x", padx=16)

        buttons = [
            ("🚀  오늘 발행 (4개)", "#a6e3a1", "#1e1e2e",
             lambda: self._run(["--count", "4", "--publish"])),
            ("✅  테스트 발행 (1개)", "#a6e3a1", "#1e1e2e",
             lambda: self._run(["--count", "1", "--publish"])),
            ("🧪  Mock 테스트 (발행X)", "#89b4fa", "#1e1e2e",
             lambda: self._run(["--count", "1", "--mock"])),
            ("📋  큐 확인", "#fab387", "#1e1e2e",
             lambda: self._run_queue(["--list"])),
            ("⚡  큐 즉시 처리", "#f38ba8", "#1e1e2e",
             lambda: self._run_queue([])),
            ("📊  발행 현황", "#cba6f7", "#1e1e2e",
             lambda: self._run(["--list"])),
            ("🔍  미리보기", "#94e2d5", "#1e1e2e",
             lambda: self._run(["--preview"])),
        ]

        # ── 자동발행 ON/OFF 토글 버튼 ──
        sched_frame = tk.Frame(self, bg="#1e1e2e", pady=6)
        sched_frame.pack(fill="x", padx=16)
        self.lbl_sched = tk.Label(sched_frame, text="",
                                  font=("Segoe UI", 10), bg="#1e1e2e", fg="#f9e2af")
        self.lbl_sched.pack(side="left", padx=(0, 12))
        self.btn_sched_toggle = tk.Button(
            sched_frame, text="", command=self._toggle_scheduler,
            font=("Segoe UI", 10, "bold"), relief="flat", padx=12, pady=4,
            cursor="hand2",
        )
        self.btn_sched_toggle.pack(side="left")
        self._refresh_scheduler_state()

        for i, (label, bg, fg, cmd) in enumerate(buttons):
            b = tk.Button(btn_frame, text=label, command=cmd,
                          bg=bg, fg=fg, font=("Segoe UI", 10, "bold"),
                          relief="flat", padx=12, pady=6, cursor="hand2",
                          activebackground=bg, activeforeground=fg)
            b.grid(row=i // 4, column=i % 4, padx=6, pady=4, sticky="ew")

        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)
        btn_frame.columnconfigure(3, weight=1)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16)

        # 로그 영역
        log_hdr = tk.Frame(self, bg="#1e1e2e")
        log_hdr.pack(fill="x", padx=16, pady=(8, 2))
        tk.Label(log_hdr, text="실행 로그", font=("Segoe UI", 10, "bold"),
                 bg="#1e1e2e", fg="#cdd6f4").pack(side="left")

        self.btn_stop = tk.Button(log_hdr, text="■ 중단",
                                  command=self._stop,
                                  bg="#f38ba8", fg="#1e1e2e",
                                  relief="flat", padx=8, cursor="hand2",
                                  state="disabled")
        self.btn_stop.pack(side="right")

        btn_clear = tk.Button(log_hdr, text="지우기",
                              command=self._clear_log,
                              bg="#313244", fg="#cdd6f4",
                              relief="flat", padx=8, cursor="hand2")
        btn_clear.pack(side="right", padx=4)

        self.log = scrolledtext.ScrolledText(
            self, wrap="word", height=18,
            bg="#11111b", fg="#cdd6f4",
            font=("Consolas", 9),
            insertbackground="#cdd6f4",
            state="disabled"
        )
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # 진행 바
        self.progress_bar = ttk.Progressbar(self, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=16, pady=(0, 8))

    # ── 상태 갱신 ─────────────────────────────────────────────────────────────

    def _refresh_status(self):
        self.lbl_progress.config(text=_progress_summary())
        self.lbl_queue.config(text=_queue_summary())

    # ── 로그 출력 ─────────────────────────────────────────────────────────────

    def _log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    # ── 프로세스 실행 ─────────────────────────────────────────────────────────

    def _run(self, extra_args: list):
        self._launch([PYTHON, str(BASE_DIR / "daily_generate.py")] + extra_args)

    def _run_queue(self, extra_args: list):
        self._launch([PYTHON, str(BASE_DIR / "activate_queue.py")] + extra_args)

    def _launch(self, cmd: list):
        if self._running:
            messagebox.showwarning("실행 중", "이미 작업이 실행 중입니다.")
            return
        self._running = True
        self.btn_stop.config(state="normal")
        self.progress_bar.start(10)
        ts = datetime.now().strftime("%H:%M:%S")
        self._log(f"\n{'─'*50}\n[{ts}] 실행: {' '.join(cmd[2:])}\n{'─'*50}\n")
        self._proc = None
        threading.Thread(target=self._worker, args=(cmd,), daemon=True).start()

    def _worker(self, cmd: list):
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(BASE_DIR),
            )
            for line in self._proc.stdout:
                self.after(0, self._log, line)
            self._proc.wait()
            rc = self._proc.returncode
            self.after(0, self._log, f"\n[완료] 종료코드: {rc}\n")
        except Exception as e:
            self.after(0, self._log, f"\n[오류] {e}\n")
        finally:
            self._running = False
            self._proc = None
            self.after(0, self._on_done)

    def _on_done(self):
        self.progress_bar.stop()
        self.btn_stop.config(state="disabled")
        self._refresh_status()

    def _stop(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._log("\n[사용자 중단]\n")
            except Exception:
                pass

    def _refresh_scheduler_state(self):
        """Task Scheduler 상태 읽어서 라벨+버튼 업데이트."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ScheduledTask -TaskName 'EtsyActivateQueue').State"],
                capture_output=True, text=True, timeout=5
            )
            state = result.stdout.strip()
        except Exception:
            state = "Unknown"

        if state == "Ready":
            self.lbl_sched.config(text="⏰ 자동발행: 활성 (매시간)", fg="#a6e3a1")
            self.btn_sched_toggle.config(
                text="⏸  자동발행 중단", bg="#f38ba8", fg="#1e1e2e",
                activebackground="#f38ba8")
        elif state == "Disabled":
            self.lbl_sched.config(text="⛔ 자동발행: 중단됨", fg="#f38ba8")
            self.btn_sched_toggle.config(
                text="▶  자동발행 재개", bg="#a6e3a1", fg="#1e1e2e",
                activebackground="#a6e3a1")
        else:
            self.lbl_sched.config(text=f"❓ 자동발행: {state}", fg="#f9e2af")
            self.btn_sched_toggle.config(
                text="↺ 상태 새로고침", bg="#89b4fa", fg="#1e1e2e",
                activebackground="#89b4fa")

    def _toggle_scheduler(self):
        """EtsyActivateQueue Task Scheduler 활성/비활성 토글."""
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "(Get-ScheduledTask -TaskName 'EtsyActivateQueue').State"],
                capture_output=True, text=True, timeout=5
            )
            state = result.stdout.strip()
        except Exception:
            state = "Unknown"

        if state == "Ready":
            subprocess.run(
                ["powershell", "-Command",
                 "Disable-ScheduledTask -TaskName 'EtsyActivateQueue'"],
                capture_output=True, timeout=10
            )
            self._log("[자동발행 중단] Task Scheduler 비활성화됨\n")
        else:
            subprocess.run(
                ["powershell", "-Command",
                 "Enable-ScheduledTask -TaskName 'EtsyActivateQueue'"],
                capture_output=True, timeout=10
            )
            self._log("[자동발행 재개] Task Scheduler 활성화됨\n")

        self._refresh_scheduler_state()


# ── 엔트리포인트 ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
