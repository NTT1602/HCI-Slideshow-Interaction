"""Chỉ số từ (Observation.truth, Decision). truth = "cmd:next"... nghĩa là người dùng chủ ý ra lệnh; khác = nền."""
from __future__ import annotations

from statistics import median

from ..datatypes import ACCEPT, UNCERTAIN


def _intervals(obs_list):
    out, cur = [], None
    for o in obs_list:
        tr = o.truth or ""
        if tr.startswith("cmd:"):
            if cur and cur["cmd"] == tr[4:]:
                cur["end"] = o.t_ms
            else:
                cur = {"cmd": tr[4:], "start": o.t_ms, "end": o.t_ms, "accepts": [], "unc": False}
                out.append(cur)
        else:
            cur = None
    return out


def evaluate(obs_list, decisions, grace_ms: int = 800) -> dict:
    ivs = _intervals(obs_list)
    false_triggers = duplicates = 0
    for d in decisions:
        iv = next((i for i in ivs if i["start"] <= d.t_ms <= i["end"] + grace_ms), None)
        if d.verdict == ACCEPT:
            if iv is None:
                false_triggers += 1
            else:
                if iv["accepts"]:
                    duplicates += 1
                iv["accepts"].append(d)
        elif d.verdict == UNCERTAIN and iv is not None:
            iv["unc"] = True
    hits = sum(1 for i in ivs if i["accepts"] and i["accepts"][0].command == i["cmd"])
    wrong = sum(1 for i in ivs if i["accepts"] and i["accepts"][0].command != i["cmd"])
    lat = [i["accepts"][0].t_ms - i["start"] for i in ivs if i["accepts"] and i["accepts"][0].command == i["cmd"]]
    hours = (obs_list[-1].t_ms - obs_list[0].t_ms) / 3600000.0 if len(obs_list) > 1 else 0.0
    return {
        "intents": len(ivs), "hits": hits, "wrong": wrong, "missed": len(ivs) - hits - wrong,
        "recall": hits / len(ivs) if ivs else None,
        "missed_with_uncertain": sum(1 for i in ivs if not i["accepts"] and i["unc"]),
        "false_triggers": false_triggers, "duplicates": duplicates,
        "false_per_hour": false_triggers / hours if hours else None,
        "uncertain_frames": sum(1 for d in decisions if d.verdict == UNCERTAIN),
        "median_latency_ms": median(lat) if lat else None,
    }

