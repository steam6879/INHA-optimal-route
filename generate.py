#!/usr/bin/env python3
"""
조회 시각(HH:MM) → 세 경로 비교 lookup JSON 생성.

조회 지점:
  gyodae : 경인교대입구역에서 인천1호선 탑승한 시각
  bp     : 인천1호선이 부평역에 도착한 시각 (내릴지 / 계속 탈지 결정 직전)

경로 (모두 시간표 기반):
  suin    : 원인재 환승 → 수인분당선 → 인하대역 → 도보
  express : 부평 환승 → 1호선 급행(동인천행) → 주안 → 511(상수)
  local   : 부평 환승 → 1호선 완행(인천행)   → 주안 → 511(상수)

출력 JSON: { "HH:MM": [ {r: 경로명, d: 상세, a: 도착 HH:MM, p: 1등 대비 +분}, ... ] }
  배열은 도착 빠른 순. 운행 없는 경로는 빠짐. 빈 배열이면 운행 시간 아님.

사용법:
    python3 generate.py                       # lookup*.json 6개 생성
    python3 generate.py --show 07:41          # 경인교대입구 기준 한 시각
    python3 generate.py --show 07:50 --at bp  # 부평 도착 기준 한 시각
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
DAYS = {
    "weekday": "",
    "saturday": "_sat",
    "holiday": "_hol",
}
ORIGINS = {"gyodae": "lookup", "bp": "lookup_bp"}
MAX_WAIT = 60  # 이보다 오래 기다려야 하면 운행 없음 취급 (막차 이후)


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
        if line and not line.startswith("#"):
            times.append(hm_to_min(line))
    return sorted(times)


def load_day(day: str) -> dict[str, list[int]] | None:
    files = {
        "suin": HERE / f"timetable_{day}.txt",
        "express": HERE / f"timetable_line1_express_{day}.txt",
        "local": HERE / f"timetable_line1_local_{day}.txt",
    }
    if not all(p.exists() for p in files.values()):
        return None
    return {k: load_timetable(p) for k, p in files.items()}


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


def evaluate(t: int, tt: dict, cfg: dict, origin: str) -> list[dict]:
    """t = 경인교대입구 탑승 시각(분). 경로별 학교 도착 시각 목록(빠른 순)."""
    c, s, l1 = cfg["common"], cfg["route_suin"], cfg["route_line1"]
    bp = origin == "bp"
    opts = []

    # 수인분당선
    platform = t + c["ride_gyodae_to_woninjae"] + s["transfer_woninjae"]
    tr = next_train(tt["suin"], platform)
    if tr is not None:
        opts.append({
            "key": "suin",
            "r": ("계속 타기 → " if bp else "") + s["label"],
            "d": f"원인재 {min_to_hm(tr)} (대기 {tr - platform}분)",
            "arr": tr + s["ride_woninjae_to_inhadae"] + s["walk_inhadae_to_school"],
        })

    # 1호선 급행 / 완행
    bp_platform = t + c["ride_gyodae_to_bupyeong"] + l1["transfer_bupyeong"]
    for key, ride in (("express", l1["express_ride_bupyeong_to_juan"]),
                      ("local", l1["local_ride_bupyeong_to_juan"])):
        tr = next_train(tt[key], bp_platform)
        if tr is None:
            continue
        opts.append({
            "key": key,
            "r": ("내리기 → " if bp else "") + l1[f"{key}_label"],
            "d": f"부평 {min_to_hm(tr)} (대기 {tr - bp_platform}분)",
            "arr": tr + ride + l1["juan_to_school"],
        })

    # 정렬: 도착 빠른 순. 수인분당선은 margin 만큼 불리하게 비교
    margin = cfg["decision"]["suin_margin"]
    opts.sort(key=lambda o: (o["arr"] + (margin if o["key"] == "suin" else 0), o["key"] != "suin"))
    return opts


def to_json(opts: list[dict]) -> list[dict]:
    if not opts:
        return []
    best = opts[0]["arr"]
    return [{"r": o["r"], "d": o["d"], "a": min_to_hm(o["arr"]), "p": o["arr"] - best} for o in opts]


def to_text(opts: list[dict]) -> str:
    if not opts:
        return "운행 시간 아님"
    rows = to_json(opts)
    return "  /  ".join(
        f"{'★' if i == 0 else ''}{x['r']}: {x['d']} → {x['a']}" + (f" (+{x['p']})" if i else "")
        for i, x in enumerate(rows)
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", metavar="HH:MM", help="해당 시각 결과만 출력(평일)")
    ap.add_argument("--at", choices=list(ORIGINS), default="gyodae", help="조회 지점")
    args = ap.parse_args()

    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

    if args.show:
        tt = load_day("weekday")
        print(to_text(evaluate(gyodae_time(hm_to_min(args.show), args.at, cfg), tt, cfg, args.at)))
        return

    for day, suffix in DAYS.items():
        tt = load_day(day)
        if tt is None:
            print(f"skip {day}: 시간표 파일 없음", file=sys.stderr)
            continue
        for origin, prefix in ORIGINS.items():
            table, wins = {}, {"suin": 0, "express": 0, "local": 0}
            for t in range(24 * 60):
                opts = evaluate(gyodae_time(t, origin, cfg), tt, cfg, origin)
                table[min_to_hm(t)] = to_json(opts)
                if opts:
                    wins[opts[0]["key"]] += 1
            dst = f"{prefix}{suffix}.json"
            (HERE / dst).write_text(json.dumps(table, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"{dst}: 1순위 분포 {wins}")


if __name__ == "__main__":
    main()
