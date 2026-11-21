from __future__ import annotations

from pathlib import Path

from .status_model import CMD_VI

ASSETS = Path(__file__).parent / "assets"
SIZES = (240, 360, 480, 600)   
FRAME_MS = 500                 

# key (khớp nhãn model / external_labels), tiêu đề, cách làm, các khung ảnh
GESTURES = [
    {"key": "swipe_left", "title": "Vuốt trái",
     "how": "Mở bàn tay, vuốt từ PHẢI sang TRÁI.", "frames": ["swipe_left_1.png", "swipe_left_2.png"],
     "command": "Chuyển sang slide trước."},
    {"key": "swipe_right", "title": "Vuốt phải",
     "how": "Mở bàn tay, vuốt từ TRÁI sang PHẢI.", "frames": ["swipe_right_1.png", "swipe_right_2.png"],
     "command": "Chuyển sang slide tiếp theo"},
    {"key": "like", "title": "Like",
     "how": "Nắm tay, ngón cái chìa LÊN, giữ yên khoảng 0,5 giây.", "frames": ["like.png"],
     "command": "Vào chế độ trình chiếu"},
    {"key": "dislike", "title": "Dislike",
     "how": "Nắm tay, ngón cái chìa XUỐNG..", "frames": ["dislike.png"],
     "command": "Thoát chế độ trình chiếu"},
]


def command_text(gesture: dict, labels: dict) -> str:
    """Dòng "Lệnh: ..." của một cử chỉ: lấy từ external_labels trong config (vuốt) hoặc ghi chú cố định (like/dislike)."""
    if gesture.get("command"):
        return "Lệnh: " + gesture["command"]
    cmd = (labels or {}).get(gesture["key"])
    return "Lệnh: " + CMD_VI.get(cmd, cmd) if cmd else ""


def pick_size(avail: int) -> int:
    """Cỡ ảnh lớn nhất không vượt `avail` px (tối thiểu cỡ nhỏ nhất)."""
    fit = [s for s in SIZES if s <= avail]
    return fit[-1] if fit else SIZES[0]


class GuidePanel:
    """Khung hướng dẫn, nhúng vào cửa sổ cha. show()/hide() bật tắt; hide() dừng hoạt ảnh."""

    def __init__(self, tk, parent, labels: dict = None):
        self.tk, self.labels = tk, labels or {}
        self.idx, self.frame_i, self.size, self.visible, self._job = 0, 0, SIZES[0], False, None
        self.images = {}                          # giữ tham chiếu PhotoImage, nếu không Tk sẽ xóa ảnh
        f = self.frame = tk.Frame(parent, bd=1, relief="groove")
        self.step = tk.Label(f, fg="#6b7280", font=("Bahnschrift", 10))
        self.step.pack(pady=(8, 0))
        self.name = tk.Label(f, font=("Bahnschrift", 15, "bold"))
        self.name.pack()
        self.pic = tk.Label(f)
        self.pic.pack(padx=12, pady=6, expand=True)
        self.how = tk.Label(f, wraplength=280, justify="center")
        self.how.pack(padx=10)
        self.cmd = tk.Label(f, fg="#2563eb", font=("Bahnschrift", 10, "bold"), wraplength=280, justify="center")
        self.cmd.pack(pady=(2, 0))
        row = tk.Frame(f)
        row.pack(pady=8)
        tk.Button(row, text="‹ Trước", width=9, command=lambda: self.go(-1)).pack(side="left", padx=6)
        tk.Button(row, text="Sau ›", width=9, command=lambda: self.go(1)).pack(side="left", padx=6)
        f.bind("<Configure>", self._resize)
        parent.winfo_toplevel().bind("<Left>",  self._arrow, add="+")
        parent.winfo_toplevel().bind("<Right>", self._arrow, add="+")

    def _arrow(self, e):
        if not self.visible:          # only flip pages while the guide is showing
            return
        self.go(-1 if e.keysym == "Left" else 1)

    # --- bật / tắt ---
    def show(self, grid: dict = None) -> None:
        if grid:
            self.frame.grid(**grid)
        else:
            self.frame.pack(fill="both", expand=True, padx=14, pady=4)
        self.visible = True
        self._refresh()

    def hide(self) -> None:
        self._cancel()
        self.frame.grid_forget()
        self.frame.pack_forget()
        self.visible = False

    # --- nội dung ---
    def go(self, step: int) -> None:
        self.idx = (self.idx + step) % len(GESTURES)
        self._refresh()

    def _refresh(self) -> None:
        self._cancel()
        g = GESTURES[self.idx]
        self.frame_i = 0
        self.step.config(text=f"Cử chỉ {self.idx + 1} / {len(GESTURES)}")
        self.name.config(text=g["title"])
        self.how.config(text=g["how"])
        self.cmd.config(text=command_text(g, self.labels))
        self._draw()

    def _image(self, filename: str):
        key = (self.size, filename)
        if key not in self.images:
            self.images[key] = self.tk.PhotoImage(file=str(ASSETS / str(self.size) / filename))
        return self.images[key]

    def _draw(self) -> None:
        g = GESTURES[self.idx]
        self.pic.config(image=self._image(g["frames"][self.frame_i]))
        if len(g["frames"]) > 1 and self.visible:   # cử chỉ động: đổi khung mỗi 0,5 giây
            self.frame_i = (self.frame_i + 1) % len(g["frames"])
            self._job = self.frame.after(FRAME_MS, self._draw)

    def _cancel(self) -> None:
        if self._job:
            self.frame.after_cancel(self._job)
            self._job = None

    def _resize(self, _event=None) -> None:
        slack = self.frame.winfo_height() - self.frame.winfo_reqheight()
        avail = min(self.size + slack, self.frame.winfo_width() - 30)
        new = pick_size(avail)
        wrap = max(220, self.frame.winfo_width() - 30)
        self.how.config(wraplength=wrap)
        self.cmd.config(wraplength=wrap)
        if new != self.size:
            self.size = new
            self._draw()
