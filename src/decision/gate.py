"""Khối: Intent Gate (xử lý Midas Touch).

IDLE --(cử chỉ ARM đủ lâu)--> ARMED --(cử chỉ lệnh rõ, giữ đủ lâu)--> COMMAND --> EXECUTE --> COOLDOWN --> IDLE
Mỗi khung trả về một Decision: ACCEPT (chỉ khi EXECUTE) | REJECT | UNCERTAIN (chỉ policy có abstain).
"""
from __future__ import annotations

from ..config import Config
from ..datatypes import (ACCEPT, ARM_LABEL, ARMED, COMMAND, CONFIRM, CONFIRM_NO, CONFIRM_YES, COOLDOWN, EXECUTE, IDLE, REJECT, UNCERTAIN,
                     Decision, FeatureWindow, Hypothesis)
from .policies import Context, get_policy

OPPOSITE = {"next": "previous", "previous": "next"}


class IntentGate:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.policy = get_policy(cfg.policy)
        self.state = IDLE
        self.arm_start = None
        self.armed_refresh = 0
        self.pending = None
        self.need_release = False
        self.cand = None            # từ teammate: GestureGate.history (nhưng theo thời gian, không đếm khung)
        self.cand_start = 0
        self.confirm_start = 0
        self.cooldown_until = 0     # từ teammate: GestureGate.cooldown (nhưng theo ms)
        self.last_swipe = (None, -10**9)  # (lệnh vuốt gần nhất, thời điểm) để chặn nhịp đưa tay về
        self.released = None        # lệnh tư thế tĩnh vừa thực hiện: phải bỏ tư thế ra rồi mới nhận lại (không lặp khi giữ tay)

    def _confirm(self, t, hyp, g, out):
        """Trạng thái CONFIRM: like (giữ confirm_hold_ms) = thực hiện lệnh đang chờ; dislike = hủy về IDLE; quá hạn = về IDLE."""
        if t - self.confirm_start > self.cfg.confirm_timeout_ms:
            self.state, self.pending, self.cand = IDLE, None, None
            return None                                   # rơi xuống xử lý như IDLE
        if not hyp.has_hand:
            self.cand = None
            return out(REJECT, "no_hand", self.pending)
        sure = hyp.probs.get(hyp.label, 0.0) >= g.min_conf
        if hyp.label == CONFIRM_NO and sure:
            cmd = self.pending
            self.state, self.pending, self.cand = IDLE, None, None
            return out(REJECT, "cancelled", cmd)
        if hyp.label == CONFIRM_YES and sure:
            if self.cand != CONFIRM_YES:
                self.cand, self.cand_start = CONFIRM_YES, t
            prog = min(1.0, (t - self.cand_start) / max(1, self.cfg.confirm_hold_ms))
            if prog >= 1.0:
                cmd, self.state = self.pending, EXECUTE
                decision = out(ACCEPT, "accepted", cmd, 1.0)
                self.state, self.pending, self.cand = COOLDOWN, None, None
                self.cooldown_until = t + self.cfg.cooldown_ms
                return decision
            return out(REJECT, "confirming", self.pending, prog)
        self.cand = None
        return out(REJECT, "confirm", self.pending)

    def __call__(self, fw: FeatureWindow, hyp: Hypothesis) -> Decision:
        t = fw.t_ms
        g = self.policy(self.cfg, Context(t, fw.speed))
        conf = hyp.probs.get(hyp.label, 0.0)

        def out(verdict, reason, cmd=None, progress=0.0):
            return Decision(t, verdict, cmd, reason, self.state, progress, hyp.label, round(conf, 4))

        if self.state == COOLDOWN:
            if t < self.cooldown_until:
                return out(REJECT, "cooldown")
            self.state, self.arm_start, self.cand = IDLE, None, None
        if self.state == CONFIRM:
            early = self._confirm(t, hyp, g, out)
            if early is not None:
                return early
        # if not g.require_arm and self.state == IDLE:
        #     self.state, self.armed_refresh = ARMED, t
        if not g.require_arm:
            if self.cfg.presence_arm_ms < 0:                       # hành vi cũ
                if self.state == IDLE:
                    self.state, self.armed_refresh = ARMED, t
            elif not hyp.has_hand:                                 # mất tay: về IDLE
                if self.state in (ARMED, COMMAND):
                    self.state = IDLE
                self.arm_start = None
            elif self.state == IDLE:                               # tay hiện đủ lâu: lên ARMED
                if self.arm_start is None:
                    self.arm_start = t
                if t - self.arm_start >= self.cfg.presence_arm_ms:
                    self.state, self.armed_refresh, self.arm_start = ARMED, t, None
        if self.state in (ARMED, COMMAND) and g.require_arm and t - self.armed_refresh > self.cfg.armed_timeout_ms:
            self.state, self.cand, self.need_release = IDLE, None, True

        if not hyp.has_hand:
            self.arm_start, self.cand, self.need_release = None, None, False
            if self.state == COMMAND:
                self.state = ARMED
            return out(REJECT, "no_hand")

        if self.state == IDLE:
            if not g.require_arm:
                prog = 0.0 if self.arm_start is None else min(1.0, (t - self.arm_start) / max(1, self.cfg.presence_arm_ms))
                return out(REJECT, "arming" if prog > 0 else "idle", progress=prog)
            if self.need_release:
                if hyp.label != ARM_LABEL:
                    self.need_release = False
                return out(REJECT, "idle")
            if hyp.label == ARM_LABEL and conf >= g.min_conf:
                if self.arm_start is None:
                    self.arm_start = t
                prog = min(1.0, (t - self.arm_start) / max(1, self.cfg.arm_hold_ms))
                if prog >= 1.0:
                    self.state, self.armed_refresh, self.arm_start = ARMED, t, None
                    return out(REJECT, "armed")
                return out(REJECT, "arming", progress=prog)
            self.arm_start = None
            return out(REJECT, "idle")

        if hyp.label == ARM_LABEL:
            self.cand, self.state = None, ARMED
            return out(REJECT, "armed")
        cmd = hyp.command
        if cmd in self.cfg.disabled_commands:
            cmd = None
        if cmd != self.released:
            self.released = None
        elif cmd is not None:
            cmd = None  # vẫn đang giữ nguyên tư thế của lệnh vừa thực hiện
        if cmd in OPPOSITE and self.last_swipe[0] == OPPOSITE[cmd] and t - self.last_swipe[1] < self.cfg.reverse_block_ms:
            cmd = None  # vuốt phải xong tay đưa về bên trái -> GRU đọc thành previous; bỏ qua chiều ngược trong một lúc
        if cmd is None or conf < self.cfg.uncertain_floor:
            self.cand, self.state = None, ARMED
            return out(REJECT, "no_command")
        if conf < g.min_conf or hyp.margin < g.min_margin:
            self.cand, self.state = None, ARMED
            reason = "low_conf" if conf < g.min_conf else "low_margin"
            return out(UNCERTAIN if g.abstain else REJECT, reason, cmd)
        if self.cand != cmd:
            self.cand, self.cand_start = cmd, t
        self.state = COMMAND
        hold = g.hold_ms
        if g.require_arm or self.cfg.policy == "swipe":  # naive giữ nguyên là mốc "không gate"
            hold = max(hold, self.cfg.command_hold_ms.get(cmd, 0))
        prog = 1.0 if hold <= 0 else min(1.0, (t - self.cand_start) / hold)
        if prog >= 1.0 and cmd in self.cfg.confirm_commands:
            self.state, self.pending, self.confirm_start, self.cand = CONFIRM, cmd, t, None
            return out(REJECT, "confirm", cmd)
        if prog >= 1.0:
            self.state = EXECUTE
            decision = out(ACCEPT, "accepted", cmd, 1.0)
            if cmd in OPPOSITE:
                self.last_swipe = (cmd, t)
            else:
                self.released = cmd
            self.state, self.cooldown_until, self.cand = COOLDOWN, t + self.cfg.cooldown_ms, None
            return decision
        return out(REJECT, "holding", cmd, prog)
