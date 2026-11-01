"""Config: dataclass + nạp từ config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace, fields

POLICIES = ("naive", "fixed", "adaptive", "abstain", "combined")


@dataclass(frozen=True)
class Config:
    policy: str = "fixed"
    recognizer: str = "rule"
    model_path: str = "models/rf.pkl"
    camera_index: int = 0
    preview_width: int = 480        # độ rộng cửa sổ camera (px)
    preview_topmost: bool = True    # cửa sổ camera luôn nổi trên cùng (để thấy HUD khi PowerPoint toàn màn hình)
    status_every_s: float = 5.0   
    dry_run: bool = True
    log_dir: str = "sessions"
    window_ms: int = 150
    arm_hold_ms: int = 300
    armed_timeout_ms: int = 4000
    conf: float = 0.80
    play_pause: int = 700  
    hold_ms: int = 400
    command_hold_ms: dict = field(default_factory=dict)
    cooldown_ms: int = 1200
    confirm_commands: list = field(default_factory=lambda: ["exit_show"])  # lệnh cần bước xác nhận (like) trước khi thực hiện
    confirm_hold_ms: int = 400
    confirm_timeout_ms: int = 4000
    margin: float = 0.25
    uncertain_floor: float = 0.40
    speed_floor: float = 0.6
    speed_gain: float = 0.08
    max_boost: float = 0.15
    hold_gain: float = 0.25
    keymap: dict = field(default_factory=lambda: {"next": "right", "previous": "left", "play_pause": "alt+p"})

    def __post_init__(self):
        if self.policy not in POLICIES:
            raise ValueError(f"policy phải thuộc {POLICIES}")

    def to_dict(self) -> dict:
        return asdict(self)

    def with_policy(self, name: str) -> "Config":
        return replace(self, policy=name)

    @staticmethod
    def from_dict(d: dict) -> "Config":
        known = {f.name for f in fields(Config)}
        return Config(**{k: v for k, v in d.items() if k in known})


def load_config(path: str = "config.yaml") -> Config:
    import yaml  # nhập muộn để test không cần pyyaml
    with open(path, encoding="utf-8") as f:
        return Config.from_dict(yaml.safe_load(f) or {})

