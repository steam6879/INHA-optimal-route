#!/usr/bin/env python3
"""
공공데이터포털 '국토교통부_(TAGO)_지하철정보' API 로 원인재역 수인분당선 시간표를 받아
timetable_*.txt 를 갱신한다. (시간표 개정 때 한 번씩 돌리면 됨)

준비:
  1. https://www.data.go.kr 에서 '국토교통부_(TAGO)_지하철정보' 활용신청 → 일반 인증키(Decoding) 복사
  2. export TAGO_KEY='발급받은키'

사용:
  python3 fetch_tago.py --list                 # 원인재 역 ID 후보 출력
  python3 fetch_tago.py --station <역ID>       # 평일/토/공휴일 txt 3개 생성
  python3 fetch_tago.py --station <역ID> --end 인천   # 종착역 이름으로 방향 필터 (기본: 인천)

※ 필드명(depTime, endSubwayStationNm 등)은 API 문서 기준. 응답이 다르면 --raw 로 확인.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "http://apis.data.go.kr/1613000/SubwayInfoService"
DAY = {"01": "timetable_weekday.txt", "02": "timetable_saturday.txt", "03": "timetable_holiday.txt"}
DAY_LABEL = {"01": "평일", "02": "토요일", "03": "일요일·공휴일"}


def call(op: str, **params) -> dict:
    key = os.environ.get("TAGO_KEY")
    if not key:
        sys.exit("TAGO_KEY 환경변수를 설정하세요.")
    params.update(serviceKey=key, _type="json", numOfRows=500, pageNo=1)
    url = f"{BASE}/{op}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    items = data["response"]["body"]["items"]
    if not items:
        return []
    items = items["item"]
    return items if isinstance(items, list) else [items]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="역 ID 후보 출력")
    ap.add_argument("--station", help="subwayStationId")
    ap.add_argument("--end", default="인천", help="이 글자가 종착역명에 포함된 열차만 (방향 필터)")
    ap.add_argument("--raw", action="store_true", help="원본 응답 출력")
    args = ap.parse_args()

    if args.list:
        for it in call("getKwrdFndSubwaySttnList", subwayStationName="원인재"):
            print(json.dumps(it, ensure_ascii=False))
        return

    if not args.station:
        sys.exit("--list 로 역 ID를 확인한 뒤 --station 으로 지정하세요.")

    for code, fname in DAY.items():
        items = []
        for ud in ("U", "D"):
            items += call(
                "getSubwaySttnAcctoSchdulList",
                subwayStationId=args.station,
                dailyTypeCode=code,
                upDownTypeCode=ud,
            )
        if args.raw:
            print(json.dumps(items, ensure_ascii=False, indent=1))
            continue

        times = set()
        for it in items:
            end = str(it.get("endSubwayStationNm", ""))
            if args.end not in end:
                continue
            dep = str(it.get("depTime") or it.get("arrTime") or "")
            if len(dep) < 4:
                continue
            hh, mm = int(dep[:2]), int(dep[2:4])
            times.add(hh * 60 + mm)

        if not times:
            print(f"{DAY_LABEL[code]}: 결과 없음 (--raw 로 필드 확인)", file=sys.stderr)
            continue

        lines = [f"# 수인분당선 원인재역 → {args.end} 방면 {DAY_LABEL[code]} (TAGO API, 역ID {args.station})"]
        lines += [f"{t // 60:02d}:{t % 60:02d}" for t in sorted(times)]
        with open(fname, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"{fname}: {len(times)}편")


if __name__ == "__main__":
    main()
