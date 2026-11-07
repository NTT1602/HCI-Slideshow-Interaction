"""Điểm vào:  python -m src live [--config config.yaml] [--policy fixed] [--send-keys]
              python -m src replay sessions/xxx.jsonl [--policies fixed,abstain]
              python -m src ui [--config config.yaml] [--policy fixed] [--no-log]"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    __package__ = "src"

try:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stderr and hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import argparse
import json
from dataclasses import replace

from .config import POLICIES, load_config


def main():
    cfg_parent = argparse.ArgumentParser(add_help=False)
    cfg_parent.add_argument("--config", default=argparse.SUPPRESS, help="Đường dẫn file cấu hình YAML (mặc định: config.yaml)")

    ap = argparse.ArgumentParser(prog="src", parents=[cfg_parent])
    sub = ap.add_subparsers(dest="cmd", required=True)

    lv = sub.add_parser("live", parents=[cfg_parent], help="Chạy nhận diện thời gian thực từ webcam")
    lv.add_argument("--policy", choices=POLICIES, help="Chiến lược gating")
    lv.add_argument("--send-keys", action="store_true", help="Gửi phím thật (mặc định là dry-run)")
    lv.add_argument("--no-log", action="store_true", help="Không ghi log session")

    ui = sub.add_parser("ui", parents=[cfg_parent], help="Mở giao diện: nút Bắt đầu, đổi TẬP/GỬI THẬT, cửa sổ trạng thái nhỏ")
    ui.add_argument("--policy", choices=POLICIES, help="Chiến lược gating")
    ui.add_argument("--no-log", action="store_true", help="Không ghi log session")

    rp = sub.add_parser("replay", parents=[cfg_parent], help="Chạy lại session đã ghi để đánh giá")
    rp.add_argument("log", help="File log jsonl")
    rp.add_argument("--policies", default=",".join(POLICIES), help="Danh sách policies cách nhau bằng dấu phẩy")

    args_to_parse = sys.argv[1:] if len(sys.argv) > 1 else ["--help"]
    a = ap.parse_args(args_to_parse)

    config_path = getattr(a, "config", "config.yaml")

    if a.cmd == "ui":
        from .ui.control_panel import run_ui
        cfg = load_config(config_path)
        if a.policy:
            cfg = cfg.with_policy(a.policy)
        run_ui(replace(cfg, dry_run=True), log=not a.no_log)  # luôn mở ở chế độ TẬP; đổi sang THẬT bằng nút
    elif a.cmd == "live":
        from .live import run_live
        cfg = load_config(config_path)
        if a.policy:
            cfg = cfg.with_policy(a.policy)
        if a.send_keys:
            cfg = replace(cfg, dry_run=False)
        run_live(cfg, log=not a.no_log)
    else:
        from .evaluation.replay import compare, load_log
        cfg, obs = load_log(a.log)
        print(json.dumps(compare(obs, cfg, a.policies.split(",")), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
