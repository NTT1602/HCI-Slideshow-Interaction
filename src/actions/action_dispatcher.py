"""Khối: thực thi lệnh. Chỉ Decision ACCEPT mới sinh phím; dry_run=True thì chỉ ghi lại."""
from __future__ import annotations

from ..config import Config
from ..datatypes import ACCEPT, Decision

ACTION_NAMES = {"next": "NEXT SLIDE", "previous": "PREVIOUS SLIDE", "play_pause": "PLAY/PAUSE", "start_show": "START SLIDESHOW", "exit_show": "EXIT SLIDESHOW"}
MODIFIERS = ("ctrl", "alt", "shift", "cmd")

def parse_key(spec: str):
    """"alt+p" -> (["alt"], "p"). Báo lỗi sớm nếu cấu hình sai."""
    parts = [p.strip().lower() for p in str(spec).split("+")]
    if not parts or not parts[-1]:
        raise ValueError(f"Phím không hợp lệ: {spec!r}")
    mods, key = parts[:-1], parts[-1]
    bad = [m for m in mods if m not in MODIFIERS]
    if bad:
        raise ValueError(f"Phím bổ trợ không hợp lệ {bad} trong {spec!r}; chỉ dùng {MODIFIERS}")
    return mods, key


class ActionDispatcher:
    def __init__(self, cfg: Config, quiet: bool = False, backend=None):
        """backend: (controller, Key) để thay pynput khi kiểm thử; mặc định dùng pynput thật khi không dry-run."""
        self.quiet = quiet
        self.keymap = cfg.keymap
        self.dry_run = cfg.dry_run
        self.sent = []  # (t_ms, phím)
        self._backend = backend
        for spec in self.keymap.values():  # kiểm tra cú pháp ngay khi khởi động
            parse_key(spec)
        if not self.dry_run:
            self._check_keys()
    
    def set_dry_run(self, flag: bool) -> None:
        """Đổi giữa tập luyện và gửi phím thật khi đang chạy. Bật gửi thật sẽ kiểm tra pynput và keymap trước."""
        if not flag:
            self._check_keys()  
        self.dry_run = flag

    def _get_backend(self):
        if self._backend is None:
            from pynput.keyboard import Controller, Key  # nhập muộn: replay/test không cần pynput
            self._backend = (Controller(), Key)
        return self._backend

    def _resolve(self, name: str):
        _, Key = self._get_backend()
        if hasattr(Key, name):
            return getattr(Key, name)
        if len(name) == 1:
            return name
        raise ValueError(f"Không có phím tên {name!r} (xem pynput.keyboard.Key)")

    def _check_keys(self):
        for spec in self.keymap.values():
            mods, key = parse_key(spec)
            for m in mods:
                self._resolve(m)
            self._resolve(key)

    def _send(self, spec: str) -> None:
        kb, _ = self._get_backend()
        mods, key = parse_key(spec)
        held = [self._resolve(m) for m in mods]
        target = self._resolve(key)
        for m in held:
            kb.press(m)
        try:
            kb.press(target)
            kb.release(target)
        finally:
            for m in reversed(held):
                kb.release(m)

    def __call__(self, dec: Decision) -> Decision:
        if dec.verdict != ACCEPT or dec.command not in self.keymap:
            return dec
        spec = self.keymap[dec.command]
        self.sent.append((dec.t_ms, spec))
        if not self.quiet:
            print(f"{ACTION_NAMES.get(dec.command, dec.command)} -> {spec}", "(dry-run, chưa gửi phím)" if self.dry_run else "")
        if not self.dry_run:
            self._send(spec)
        return dec