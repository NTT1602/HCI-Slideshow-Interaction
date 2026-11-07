from __future__ import annotations

import sys
import threading
import time

from ..config import Config
from .status_model import view_model

W, H = 100, 150          # kích thước cửa sổ trạng thái
BG, FG, MUTED = "#111827", "#f9fafb", "#cbd5e1"


def _no_activate(win) -> None:
    """Windows: cửa sổ không giành focus khi bấm vào, để phím vẫn gửi tới PowerPoint."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id()) or win.winfo_id()
        GWL_EXSTYLE, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW = -20, 0x08000000, 0x00000080
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
    except Exception:
        pass  # không có thì cửa sổ vẫn dùng được, chỉ là bấm vào sẽ lấy focus


class StatusWindow:
    """Cửa sổ nhỏ 100x150: dải chế độ (TẬP/THẬT) | ô trạng thái Intent Gate | lệnh | gợi ý | thanh tiến độ."""

    def __init__(self, tk, master, on_stop, on_toggle_mode):
        self.tk = tk
        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)            # không viền, không thanh tiêu đề
        self.win.attributes("-topmost", True)
        x = self.win.winfo_screenwidth() - W - 12
        self.win.geometry(f"{W}x{H}+{x}+12")      # góc trên phải; kéo chuột để dời
        self.canvas = tk.Canvas(self.win, width=W, height=H, bg=BG, highlightthickness=1, highlightbackground="#6b7280")
        self.canvas.pack()
        self.menu = tk.Menu(self.win, tearoff=0)
        self.menu.add_command(label="Đổi chế độ TẬP / THẬT", command=on_toggle_mode)
        self.menu.add_command(label="Dừng", command=on_stop)
        self.canvas.bind("<Button-3>", lambda e: self.menu.tk_popup(e.x_root, e.y_root))
        self.canvas.bind("<ButtonPress-1>", self._drag_start)
        self.canvas.bind("<B1-Motion>", self._drag)
        self._last = None
        _no_activate(self.win)
        self.win.after(1000, self._keep_on_top)

    def _drag_start(self, e):
        self._dx, self._dy = e.x, e.y

    def _drag(self, e):
        self.win.geometry(f"+{self.win.winfo_x() + e.x - self._dx}+{self.win.winfo_y() + e.y - self._dy}")

    def _keep_on_top(self):
        try:
            self.win.attributes("-topmost", True)
            self.win.lift()
            self.win.after(1000, self._keep_on_top)
        except Exception:
            pass  # cửa sổ đã đóng

    def draw(self, vm: dict) -> None:
        key = tuple(vm.values())
        if key == self._last:
            return
        self._last = key
        c = self.canvas
        c.delete("all")
        c.create_rectangle(0, 0, W, 18, fill=vm["mode_color"], width=0)                       # dải chế độ
        c.create_text(W // 2, 9, text=vm["mode_text"], fill="white", font=("Segoe UI", 8, "bold"))
        c.create_rectangle(0, 18, W, 74, fill=vm["color"], width=0)                           # ô trạng thái
        c.create_text(W // 2, 46, text=vm["title"], fill="white", font=("Segoe UI", 11, "bold"), width=W - 6, justify="center")
        c.create_text(W // 2, 88, text=vm["command"], fill=FG, font=("Segoe UI", 10, "bold"), width=W - 8, justify="center")
        c.create_text(W // 2, 116, text=vm["hint"], fill=MUTED, font=("Segoe UI", 8), width=W - 10, justify="center")
        c.create_rectangle(8, 141, W - 8, 146, fill="#374151", width=0)                       # thanh tiến độ
        if vm["progress"] > 0:
            c.create_rectangle(8, 141, 8 + (W - 16) * vm["progress"], 146, fill=vm["color"], width=0)

    def destroy(self):
        self.win.destroy()


class ControlApp:
    def __init__(self, cfg: Config, log: bool = True, session_factory=None):
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.cfg, self.log = cfg, log
        self.session_factory = session_factory      # để kiểm thử thay LiveSession bằng bản giả
        self.dry_run = cfg.dry_run                  # mặc định bắt đầu ở chế độ TẬP
        self.session = self.thread = self.status = None

        r = self.root = tk.Tk()
        r.title("Điều khiển cử chỉ")
        r.resizable(False, False)
        r.protocol("WM_DELETE_WINDOW", self.close)
        pad = {"padx": 14, "pady": 5, "fill": "x"}
        tk.Label(r, text="Điều khiển slide bằng cử chỉ tay", font=("Segoe UI", 12, "bold")).pack(padx=14, pady=(12, 2))
        self.start_btn = tk.Button(r, text="▶  Bắt đầu", font=("Segoe UI", 12, "bold"), bg="#16a34a", fg="white",
                                   activebackground="#15803d", activeforeground="white", command=self.toggle_run, height=2)
        self.start_btn.pack(**pad)
        self.mode_btn = tk.Button(r, font=("Segoe UI", 10, "bold"), command=self.toggle_mode, height=2)
        self.mode_btn.pack(**pad)
        self.preview_var = tk.BooleanVar(value=False)
        tk.Checkbutton(r, text="Hiện cửa sổ camera (để xem tay)", variable=self.preview_var,
                       command=self._apply_preview).pack(padx=14, anchor="w")
        self.info = tk.Label(r, text="Chưa chạy", fg="#4b5563", anchor="w", wraplength=300, justify="left")
        self.info.pack(padx=14, pady=(6, 0), fill="x")
        tk.Label(r, fg="#6b7280", anchor="w", wraplength=300, justify="left", text=(
            "TẬP: nhận lệnh nhưng không gửi phím, dùng để làm quen.\n"
            "GỬI THẬT: phím gửi vào cửa sổ đang được chọn (hãy bấm vào PowerPoint đang trình chiếu).\n"
            "Cửa sổ nhỏ góc phải hiện trạng thái; kéo để dời, chuột phải để dừng hoặc đổi chế độ.")).pack(padx=14, pady=(2, 12), fill="x")
        self._paint_mode()
        r.after(60, self._tick)

    # --- nút bấm ---
    def toggle_run(self):
        if self.session is None:
            self.start()
        else:
            self.stop()

    def start(self):
        if self.session_factory:
            self.session = self.session_factory(self.cfg, self.log, self.preview_var.get())
        else:
            from ..live import LiveSession  # nhập muộn: cv2/mediapipe chỉ nạp khi bấm Bắt đầu
            self.session = LiveSession(self.cfg, log=self.log, preview=self.preview_var.get())
        self.session.dry_run = self.dry_run
        self.thread = threading.Thread(target=self.session.run, daemon=True)
        self.thread.start()
        self.status = StatusWindow(self.tk, self.root, self.stop, self.toggle_mode)
        self.start_btn.config(text="■  Dừng", bg="#dc2626", activebackground="#b91c1c")
        self.info.config(text="Đang khởi động camera...", fg="#4b5563")

    def stop(self):
        if self.session:
            self.session.request_stop()
            self.start_btn.config(text="Đang dừng...", state="disabled")

    def toggle_mode(self):
        new = not self.dry_run
        if not new:  # sang GỬI THẬT: kiểm tra trước và hỏi lại
            try:
                import pynput.keyboard  # noqa: F401
            except Exception as e:
                self.messagebox.showerror("Không gửi được phím", f"Thiếu thư viện pynput ({e}).\nCài bằng: pip install pynput")
                return
            if not self.messagebox.askokcancel("Chuyển sang GỬI PHÍM THẬT", "Từ giờ cử chỉ sẽ gửi phím thật vào cửa sổ đang được chọn. Tiếp tục?"):
                return
        if self.session:
            try:
                self.session.set_dry_run(new)
            except Exception as e:
                self.messagebox.showerror("Không đổi được chế độ", str(e))
                return
        self.dry_run = new
        self._paint_mode()

    def _paint_mode(self):
        if self.dry_run:
            self.mode_btn.config(text="Chế độ: TẬP (không gửi phím)\nBấm để chuyển sang GỬI THẬT", bg="#f59e0b", activebackground="#d97706", fg="black")
        else:
            self.mode_btn.config(text="Chế độ: GỬI PHÍM THẬT\nBấm để quay lại TẬP", bg="#dc2626", activebackground="#b91c1c", fg="white")

    def _apply_preview(self):
        if self.session:
            self.session.preview = self.preview_var.get()

    # --- vòng cập nhật ---
    def _tick(self):
        if self.session is not None:
            if self.thread is not None and not self.thread.is_alive():
                self._finished()
            else:
                snap = self.session.snapshot()
                if self.status:
                    self.status.draw(view_model(snap, time.monotonic()))
                if snap["running"]:
                    seen = "thấy tay" if snap["hand"] > 0.3 else "chưa thấy tay"
                    self.info.config(text=f"Đang chạy · {snap['fps']:.0f} khung/s · {seen}", fg="#15803d")
        self.root.after(60, self._tick)

    def _finished(self):
        err = self.session.error
        self.session = self.thread = None
        if self.status:
            self.status.destroy()
            self.status = None
        self.start_btn.config(text="▶  Bắt đầu", bg="#16a34a", activebackground="#15803d", state="normal")
        self.info.config(text=f"Lỗi: {err}" if err else "Đã dừng", fg="#dc2626" if err else "#4b5563")

    def close(self):
        if self.session:
            self.session.request_stop()
            if self.thread:
                self.thread.join(timeout=2)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def run_ui(cfg: Config, log: bool = True):
    ControlApp(cfg, log=log).run()
