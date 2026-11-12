#!/usr/bin/env python3
"""
조회 시각(HH:MM) → 최적 경로 lookup JSON 생성.

조회 지점 두 곳:
  gyodae : 경인교대입구역에서 인천1호선 탑승한 시각
  bp     : 인천1호선이 부평역에 도착한 시각 (내릴지 / 계속 탈지 결정 직전)

  경로 A: 원인재 환승 → 수인분당선(시간표) → 인하대역 → 도보
  경로 B: 부평 환승 → 1호선 급행(시간표, 주안 정차) → 주안 → 511(상수)

사용법:
    python3 generate.py                     # lookup*.json 6개 생성
    python3 generate.py --show 07:41        # 경인교대입구 기준 한 시각
    python3 generate.py --show 07:50 --at bp  # 부평 도착 기준 한 시각
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DAYS = {
    # day: (수인분당선 시간표, 1호선 급행 시간표, 파일 접미사)
    "weekday": ("timetable_weekday.txt", "timetable_line1_express_weekday.txt", ""),
    "saturday": ("timetable_saturday.txt", "timetable_line1_express_saturday.txt", "_sat"),
    "holiday": ("timetable_holiday.txt", "timetable_line1_express_holiday.txt", "_hol"),
}
ORIGINS = {
    # origin: 파일 접두사
    "gyodae": "lookup",
    "bp": "lookup_bp",
}
MAX_WAIT = 60  # 이보다 오래 기다려야 하면 '운행 없음'으로 취급 (막차 이후)


def hm_to_min(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def min_to_hm(x: int) -> str:
    x %= 24 * 60
    return f"{x // 60:02d}:{x % 60:02d}"


def load_timetable(path: Path) -> list[int]:
    times = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        times.append(hm_to_min(line))
    return sorted(times)


def next_train(trains: list[int], t: int) -> int | None:
    for x in trains:
        if x >= t:
            return x if x - t <= MAX_WAIT else None
    return None


def gyodae_time(t: int, origin: str, cfg: dict) -> int:
    """조회 시각 t 를 '경인교대입구 탑승 시각'으로 환산."""
    if origin == "bp":
        return t - cfg["common"]["ride_gyodae_to_bupyeong"]
    return t


def evaluate(t: int, suin_tt: list[int], exp_tt: list[int], cfg: dict) -> dict:
    """t = 경인교대입구 탑승 시각(분). 두 경로의 학교 도착 시각 계산."""
    c, s, e = cfg["common"], cfg["route_suin"], cfg["route_express"]

    # --- 경로 A: 수인분당선 ---
    platform = t + c["ride_gyodae_to_woninjae"] + s["transfer_woninjae"]
    train = next_train(suin_tt, platform)
    suin = None
    if train is not None:
        suin = {
            "train": train,
            "wait": train - platform,
            "arrive": train + s["ride_woninjae_to_inhadae"] + s["walk_inhadae_to_school"],
        }

    # --- 경로 B: 1호선 급행 → 주안 → 511 ---
    bp_platform = t + c["ride_gyodae_to_bupyeong"] + e["transfer_bupyeong"]
    exp = next_train(exp_tt, bp_platform)
    cand = []
    if exp is not None:
        cand.append({"kind": "급행", "train": exp, "wait": exp - bp_platform,
                     "juan": exp + e["express_ride_bupyeong_to_juan"]})
    if e.get("local_fallback", True) and (exp is not None or train is not None):
        dep = bp_platform + e["local_avg_wait"]
        cand.append({"kind": "일반", "train": dep, "wait": e["local_avg_wait"],
                     "juan": dep + e["local_ride_bupyeong_to_juan"]})
    express = None
    if cand:
        best = min(cand, key=lambda x: x["juan"])
        best["arrive"] = best["juan"] + e["juan_to_school"]
        express = best

    return {"suin": suin, "express": express}


def render(r: dict, cfg: dict, origin: str) -> str:
    s, x = r["suin"], r["express"]
    margin = cfg["decision"]["suin_margin"]
    if origin == "bp":
        L_s, L_x = "계속 타기 → 수인분당선", "내리기 → 급행+511"
    else:
        L_s, L_x = cfg["route_suin"]["label"], cfg["route_express"]["label"]

    suin_txt = None if s is None else \
        f"원인재 {min_to_hm(s['train'])} (대기 {s['wait']}분) → {min_to_hm(s['arrive'])}"
    exp_txt = None if x is None else \
        f"부평 {x['kind']} {min_to_hm(x['train'])} (대기 {x['wait']}분) → {min_to_hm(x['arrive'])}"

    if s is None and x is None:
        return "⚫ 운행 시간 아님"
    if s is None:
        return f"🔵 {L_x} | {exp_txt} | 수인분당선 운행 없음"
    if x is None:
        return f"🟢 {L_s} | {suin_txt} | 1호선 운행 없음"

    diff = x["arrive"] - s["arrive"]  # 양수면 수인분당선이 빠름
    if diff >= margin:
        return f"🟢 {L_s} | {suin_txt} | {L_x} {exp_txt} (+{diff}분)"
    return f"🔵 {L_x} | {exp_txt} | {L_s} {suin_txt} (+{-diff}분)"


def build(suin_tt, exp_tt, cfg, origin) -> dict[str, str]:
    out = {}
    for t in range(24 * 60):
        r = evaluate(gyodae_time(t, origin, cfg), suin_tt, exp_tt, cfg)
        out[min_to_hm(t)] = render(r, cfg, origin)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", metavar="HH:MM", help="해당 시각 결과만 출력(평일)")
    ap.add_argument("--at", choices=list(ORIGINS), default="gyodae", help="조회 지점")
    args = ap.parse_args()

    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

    if args.show:
        s_src, e_src, _ = DAYS["weekday"]
        t = gyodae_time(hm_to_min(args.show), args.at, cfg)
        r = evaluate(t, load_timetable(HERE / s_src), load_timetable(HERE / e_src), cfg)
        print(render(r, cfg, args.at))
        return

    for day, (s_src, e_src, suffix) in DAYS.items():
        if not (HERE / s_src).exists() or not (HERE / e_src).exists():
            print(f"skip {day}: 시간표 파일 없음", file=sys.stderr)
            continue
        suin_tt, exp_tt = load_timetable(HERE / s_src), load_timetable(HERE / e_src)
        for origin, prefix in ORIGINS.items():
            dst = f"{prefix}{suffix}.json"
            table = build(suin_tt, exp_tt, cfg, origin)
            (HERE / dst).write_text(json.dumps(table, ensure_ascii=False, indent=0), encoding="utf-8")
            n = sum(v.startswith("🟢") for v in table.values())
            print(f"{dst}: 1440분 중 수인분당선 추천 {n}분")


if __name__ == "__main__":
    main()
