from __future__ import annotations

CMD_VI = {"next": "Slide tiếp", "previous": "Slide trước", "play_pause": "Phát / dừng", "start_show": "Vào trình chiếu", "exit_show": "Thoát"}
LAST_CMD_SHOW_S = 1.5 
STATE_VIEW = {
    "IDLE": ("CHỜ", "#505050", "Mở bàn tay để bắt đầu"),
    "ARMED": ("SẴN SÀNG", "#14AA4B", "Làm cử chỉ lệnh"),
    "COMMAND": ("GIỮ YÊN", "#0F7F36", "Giữ cử chỉ thêm chút"),
    "UNCERTAIN": ("CHƯA CHẮC", "#FF6A00", "Giữ rõ hơn"),
    "REJECT": ("KHÔNG RÕ", "#DC2828", "Thử lại"),
    "CONFIRM": ("XÁC NHẬN", "#D2AA06", "Like = Có, Dislike = Không"),
    "EXECUTE": ("ĐÃ NHẬN", "#2864EB", ""),
    "COOLDOWN": ("NGHỈ", "#6D28D9", "Chờ giây lát"),
}
OFF_COLOR = "#374151"
MODE_VIEW = {True: ("● TẬP", "#D2AA06"), False: ("● GỬI THẬT", "#3FA9F5")}


def view_model(snap: dict, now: float) -> dict:
    """snap: LiveSession.snapshot(). Trả về dict: title, color, command, hint, progress, mode_text, mode_color."""
    mode_text, mode_color = MODE_VIEW[bool(snap.get("dry_run", True))]
    base = {"command": "", "progress": 0.0, "mode_text": mode_text, "mode_color": mode_color}
    if not snap.get("running"):
        if snap.get("starting"):
            return {**base, "title": "KHỞI ĐỘNG", "color": OFF_COLOR, "hint": "Đang mở camera..."}
        return {**base, "title": "TẮT", "color": OFF_COLOR, "hint": "Bấm Bắt đầu"}

    hud = snap.get("hud") or {}
    state = hud.get("state", "IDLE")
    title, color, hint = STATE_VIEW.get(state, STATE_VIEW["IDLE"])
    progress = float(hud.get("progress") or 0.0)
    if state == "IDLE" and hud.get("reason") == "arming":
        hint = "Giữ bàn tay mở..."
    if state == "EXECUTE":
        hint = "Chưa gửi phím (đang tập)" if snap.get("dry_run", True) else "Đã gửi phím"
        if not snap.get("dry_run", True):
            title = "ĐÃ GỬI"

    command = ""
    if state in ("COMMAND", "CONFIRM", "EXECUTE") and hud.get("command"):
        command = CMD_VI.get(hud["command"], hud["command"])
    elif snap.get("last_command") and (snap.get("last_command_age") or 99) <= LAST_CMD_SHOW_S:
        command = CMD_VI.get(snap["last_command"], snap["last_command"])
    if state == "CONFIRM" and command:
        command += "?"
    return {**base, "title": title, "color": color, "command": command, "hint": hint, "progress": max(0.0, min(1.0, progress))}
