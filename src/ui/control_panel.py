from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from ..config import Config
from .status_model import view_model

W, H = 100, 150          # kích thước cửa sổ trạng thái
BG, FG, MUTED = "#111827", "#eef2f7", "#cbd5e1"

# [1] Consistency: cả 3 nút dùng chung một cỡ chữ và một chiều cao
BTN_FONT = ("Bahnschrift", 11, "bold")
BTN_H = 54               # px
CARD = "#eef2f7"
TEXTURE = Path(__file__).parent / "assets" / "texture" / "paper.png"


class TiledBackground:
    """[3] Texture nền: lặp ô ảnh nhỏ phủ kín cửa sổ, dựng lại khi đổi cỡ (chờ 60 ms cho đỡ giật)."""

    def __init__(self, tk, root, path=TEXTURE):
        self.tk, self.root = tk, root
        self.tile = tk.PhotoImage(file=str(path))
        self.label = tk.Label(root, bd=0)
        self.label.place(x=0, y=0, relwidth=1, relheight=1)
        self.label.lower()                                   # nằm dưới mọi widget khác
        self.image, self._size, self._job = None, (0, 0), None
        root.bind("<Configure>", self._schedule, add="+")

    def _schedule(self, event):
        if event.widget is not self.root:
            return
        if self._job:
            self.root.after_cancel(self._job)
        self._job = self.root.after(60, self._rebuild)

    def _rebuild(self):
        self._job = None
        size = (self.root.winfo_width(), self.root.winfo_height())
        if size == self._size or min(size) < 2:
            return
        self._size = size
        img = self.tk.PhotoImage(width=size[0], height=size[1])
        self.root.tk.call(img, "copy", self.tile, "-to", 0, 0, size[0], size[1])   # lặp ô texture
        self.label.config(image=img)
        self.image = img                                     # giữ tham chiếu, nếu không ảnh bị xóa


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
        c.create_text(W // 2, 9, text=vm["mode_text"], fill="white", font=("Bahnschrift", 10, "bold"))
        c.create_rectangle(0, 18, W, 74, fill=vm["color"], width=0)                           # ô trạng thái
        c.create_text(W // 2, 46, text=vm["title"], fill="white", font=("Bahnschrift", 12, "bold"), width=W - 6, justify="center")
        c.create_text(W // 2, 88, text=vm["command"], fill=FG, font=("Bahnschrift", 10, "bold"), width=W - 8, justify="center")
        c.create_text(W // 2, 116, text=vm["hint"], fill=MUTED, font=("Bahnschrift", 10), width=W - 10, justify="center")
        c.create_rectangle(8, 141, W - 8, 146, fill="#374151", width=0)                       # thanh tiến độ
        if vm["progress"] > 0:
            c.create_rectangle(8, 141, 8 + (W - 16) * vm["progress"], 146, fill=vm["color"], width=0)

    def destroy(self):
        self.win.destroy()


class ControlApp:
    def __init__(self, cfg: Config, log: bool = True, session_factory=None, maximized: bool = False):
        import tkinter as tk
        from tkinter import messagebox
        self.tk, self.messagebox = tk, messagebox
        self.cfg, self.log = cfg, log
        self.session_factory = session_factory      # để kiểm thử thay LiveSession bằng bản giả
        self.dry_run = cfg.dry_run                  # mặc định bắt đầu ở chế độ TẬP
        self.session = self.thread = self.status = self.guide = None

        r = self.root = tk.Tk()
        r.title("HGISS")
        r.resizable(True, True)       # cho phép kéo giãn / phóng to kín màn hình (nút phóng to trên thanh tiêu đề)
        r.minsize(340, 420)
        r.columnconfigure(1, weight=1)   # cột phải (hướng dẫn) giãn khi cửa sổ lớn
        r.rowconfigure(0, weight=1)
        try:
            self.bg = TiledBackground(tk, r)         # nền texture
        except tk.TclError:
            self.bg = None 
        r.option_add("*Label.Background", CARD)
        r.option_add("*Checkbutton.Background", CARD)
        r.option_add("*Checkbutton.activeBackground", CARD)
        left = tk.Frame(r, bg=CARD)      # cột trái: thẻ trắng nằm trên nền texture
        left.grid(row=0, column=0, sticky="n", padx=14, pady=14)
        r.protocol("WM_DELETE_WINDOW", self.close)
        TITLE_IMG = Path(__file__).parent / "assets" / "texture" / "label.png"   # đặt cạnh TEXTURE ở đầu file
        self.title_img = tk.PhotoImage(file=str(TITLE_IMG))       # phải gán vào self, nếu không ảnh bị xóa và nhãn trống
        tk.Label(left, image=self.title_img, bd=0).pack(padx=14, pady=(12, 6))                                          # thiếu ảnh thì quay về chữ như cũ
        tk.Label(left, text="Hệ thống điều khiển slide bằng cử chỉ tay", font=("Bahnschrift", 16, "bold")).pack(padx=14, pady=(2, 2))
        tk.Label(left, text="Hand-Gesture Interaction Slideshow System", font=("Bahnschrift", 14, "italic")).pack(padx=14, pady=(2, 2))
        self.start_btn = self._button(left, text="▶️  Bắt đầu  (S)", bg="#16a34a", fg="white",
                                      activebackground="#15803d", activeforeground="white", command=self.toggle_run)
        self.mode_btn = self._button(left, command=self.toggle_mode)
        self.guide_btn = self._button(left, text="ℹ️  Hướng dẫn cử chỉ  (G)  ▶", bg="#e5e7eb", activebackground="#d1d5db",
                                      command=self.toggle_guide)
        self.preview_var = tk.BooleanVar(value=False)
        tk.Checkbutton(left, text="Hiện cửa sổ camera (C)", variable=self.preview_var,
                       command=self._apply_preview).pack(padx=14, anchor="w")
        self.info = tk.Label(left, text="Chưa chạy", fg="#4b5563", anchor="w", wraplength=300, justify="left")
        self.info.pack(padx=14, pady=(6, 0), fill="x")
        tk.Label(left, fg="#6b7280", anchor="w", wraplength=300, justify="left", text=(
            "TẬP: nhận lệnh nhưng không gửi phím, dùng để làm quen.\n"
            "GỬI THẬT: phím gửi vào cửa sổ đang được chọn (hãy bấm vào PowerPoint đang trình chiếu).\n"
            "Cửa sổ nhỏ góc phải hiện trạng thái; kéo để dời, chuột phải để dừng hoặc đổi chế độ.")).pack(padx=14, pady=(2, 12), fill="x")
        self._paint_mode()
        r.bind("<Key>", self._on_key)    # [2] phím tắt
        if maximized:
            self.maximize(True)
        r.after(60, self._tick)

    def _button(self, parent, **opts):
        """[1] Nút cùng cỡ: Frame cao cố định (không co theo chữ) + nút lấp đầy Frame + fill="x" cho cùng chiều rộng."""
        box = self.tk.Frame(parent, height=BTN_H, bg=CARD)
        box.pack_propagate(False)
        btn = self.tk.Button(box, font=BTN_FONT, bd=0, relief="flat", cursor="hand2", **opts)
        btn.pack(fill="both", expand=True)
        box.pack(padx=14, pady=5, fill="x")
        return btn

    def _on_key(self, e):
        """[2] S = Bắt đầu/Dừng · M = đổi chế độ · G = hướng dẫn · C = bật/tắt cửa sổ camera."""
        k = (e.keysym or "").lower()
        if k == "s" and str(self.start_btn["state"]) != "disabled":
            self.toggle_run()
        elif k == "m":
            self.toggle_mode()
        elif k == "g":
            self.toggle_guide()
        elif k == "c":
            self.preview_var.set(not self.preview_var.get())
            self._apply_preview()

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
        self.start_btn.config(text="⏹️  Dừng  (S)", bg="#dc2626", activebackground="#b91c1c")
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

    def toggle_guide(self):
        """Bật / tắt phần hướng dẫn cử chỉ ngay trong cửa sổ này (không mở cửa sổ mới)."""
        if self.guide is None:
            from .gesture_guide import GuidePanel  # nhập muộn
            self.guide = GuidePanel(self.tk, self.root, labels=getattr(self.cfg, "external_labels", {}))
        if self.guide.visible:
            self.guide.hide()
            self.guide_btn.config(text="ℹ️  Hướng dẫn cử chỉ  (G) ◀")
        else:
            self.guide.show(grid=dict(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14))  # cột phải của cùng cửa sổ
            self.guide_btn.config(text="ℹ️  Hướng dẫn cử chỉ  (G) ▶")

    def maximize(self, on: bool = True):
        """Phóng to kín màn hình (vẫn thấy thanh tiêu đề và thanh tác vụ, khác với toàn màn hình F11)."""
        try:
            self.root.state("zoomed" if on else "normal")        # Windows, macOS
        except self.tk.TclError:
            self.root.attributes("-zoomed", on)
        
    def _paint_mode(self):
        if self.dry_run:
            self.mode_btn.config(text="Chế độ: TẬP (không gửi phím)\nBấm để chuyển sang GỬI THẬT  (M)", bg="#f59e0b", activebackground="#d97706", fg="black")
        else:
            self.mode_btn.config(text="Chế độ: GỬI PHÍM THẬT\nBấm để quay lại TẬP  (M)", bg="#dc2626", activebackground="#b91c1c", fg="white")

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
        self.start_btn.config(text="▶  Bắt đầu  (S)", bg="#16a34a", activebackground="#15803d", state="normal")
        self.info.config(text=f"Lỗi: {err}" if err else "Đã dừng", fg="#dc2626" if err else "#4b5563")

    def close(self):
        if self.session:
            self.session.request_stop()
            if self.thread:
                self.thread.join(timeout=2)
        self.root.destroy()

    def run(self):
        self.root.mainloop()

def run_ui(cfg: Config, log: bool = True, maximized: bool = False):
    ControlApp(cfg, log=log, maximized=maximized).run()
