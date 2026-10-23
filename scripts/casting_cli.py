#!/usr/bin/env python3
"""Choose a casting source before running the existing Liuyao Najia calculator."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import liuyao_cli as najia

BEIJING = timezone(timedelta(hours=8))
DEFAULT_METHOD = "time_traditional"
METHODS = (
    {"id": "time_traditional", "label": "按当前时间：传统年月日时法", "recommended": True},
    {"id": "random", "label": "程序随机生成六组三币记录", "recommended": False},
    {"id": "time_seed", "label": "当前时间作种子生成六组", "recommended": False},
)
TRIGRAM_BITS = ("111", "110", "101", "100", "011", "010", "001", "000")
ENCODING = {6: "000", 7: "001", 8: "011", 9: "111"}
STAMP_PATTERN = r"\d{4}-\d{2}-\d{2}T(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)"

def current_time():
    return datetime.now(BEIJING)

def civil_time(stamp):
    if not isinstance(stamp, str) or re.fullmatch(STAMP_PATTERN, stamp) is None:
        raise ValueError("cast_time requires date, hour, minute and explicit UTC offset")
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(BEIJING)

def traditional_values(year_number, month_number, day_number, hour_number):
    """Year/hour branches are numbered Zi=1 through Hai=12."""
    if not (1 <= year_number <= 12 and 1 <= month_number <= 12
            and 1 <= day_number <= 30 and 1 <= hour_number <= 12):
        raise ValueError("Invalid lunar date or branch number")
    upper_sum = year_number + month_number + day_number
    total = upper_sum + hour_number
    upper, lower, moving = (upper_sum - 1) % 8 + 1, (total - 1) % 8 + 1, (total - 1) % 6 + 1
    bits = TRIGRAM_BITS[lower - 1] + TRIGRAM_BITS[upper - 1]
    values = [(9 if bit == "1" else 6) if i + 1 == moving
              else (7 if bit == "1" else 8) for i, bit in enumerate(bits)]
    return values, {"year_number": year_number, "month_number": month_number,
                    "day_number": day_number, "hour_number": hour_number,
                    "upper_sum": upper_sum, "total": total, "upper_number": upper,
                    "lower_number": lower, "moving_position": moving}

def traditional_cast(civil, boundary):
    from lunar_python import Solar
    date_civil = civil + timedelta(days=1) if boundary == "zi_start" and civil.hour == 23 else civil
    lunar = Solar.fromYmdHms(date_civil.year, date_civil.month, date_civil.day,
                            civil.hour, civil.minute, civil.second).getLunar()
    hour_number = (civil.hour + 1) // 2 % 12 + 1
    values, details = traditional_values(lunar.getYearZhiIndex() + 1,
                                         abs(lunar.getMonth()), lunar.getDay(), hour_number)
    details.update(lunar_year=lunar.getYear(), lunar_month=lunar.getMonth(),
                   lunar_day=lunar.getDay(), year_branch=lunar.getYearZhi(),
                   hour_branch=najia.BRANCHES[hour_number - 1],
                   lunar_date_used=date_civil.date().isoformat(),
                   leap_month=lunar.getMonth() < 0, leap_month_rule="use_number_of_repeated_month",
                   year_boundary="lunar_new_year", day_boundary=boundary)
    return [ENCODING[value] for value in values], details

def random_coins():
    return ["".join(str(secrets.randbits(1)) for _ in range(3)) for _ in range(6)]

def time_seed_coins(stamp):
    digest = hashlib.sha256(("liuyao-time-seed-v1\n" + stamp).encode("utf-8")).digest()
    bits = "".join(format(byte, "08b") for byte in digest)[:18]
    return [bits[i:i + 3] for i in range(0, 18, 3)]

def build_output(payload, *, now=None):
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object")
    unknown = set(payload) - najia.ALLOWED - {"casting_method"}
    if unknown:
        raise ValueError("Unsupported fields: " + ", ".join(sorted(unknown)))
    base = {key: value for key, value in payload.items() if key != "casting_method"}
    # A present but invalid coins field must never silently become a generated cast.
    if "coins" in base:
        result = najia.build_output(base)
        return {"status": "ready", "casting": {
            "method": "manual", "generated": False, "coins_kind": "user_coin_faces",
            "raw_coins": list(result["input"]["coins"]),
            "effective_cast_time": base.get("cast_time"),
            "time_source": "user_provided" if base.get("cast_time") is not None else "missing"
        }, **result}
    _, question = najia.validate({**base, "coins": ["001"] * 6})
    if not question:
        raise ValueError("A question is required when coins are not provided")
    boundary = base.get("day_boundary", "midnight")
    if boundary not in ("midnight", "zi_start"):
        raise ValueError("day_boundary must be midnight or zi_start")
    method = payload.get("casting_method")
    if method is None:
        return {"status": "awaiting_casting_method", "question": question,
                "request": dict(payload), "default_method": DEFAULT_METHOD,
                "prompt": "请选择起卦方式：按当前时间（传统年月日时法，默认）、程序随机六组，或时间作种子六组。选择后再排盘解卦。",
                "methods": list(METHODS)}
    if not isinstance(method, str) or method not in {item["id"] for item in METHODS}:
        raise ValueError("casting_method must be time_traditional, random or time_seed")
    if base.get("cast_time") is None:
        instant = current_time() if now is None else now
        if not isinstance(instant, datetime) or instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("Current time must be timezone-aware")
        civil = instant.astimezone(BEIJING).replace(microsecond=0)
        base["cast_time"] = civil.isoformat(timespec="seconds")
        generated_at, time_source = base["cast_time"], "program_clock"
    else:
        civil = civil_time(base["cast_time"])
        generated_at, time_source = None, "user_provided"
    stamp = civil.isoformat(timespec="seconds")
    # Reject missing calendar dependencies and invalid dates before drawing any random bits.
    najia.calendar_info(base)
    meta = {"method": method, "generated": True, "effective_cast_time": stamp,
            "time_source": time_source, "generated_at": generated_at,
            "timezone": "UTC+08:00", "time_precision": "second",
            "chart_interpretation": "liuyao_najia"}
    if method == "time_traditional":
        coins, details = traditional_cast(civil, boundary)
        meta.update(algorithm="meihua_ymdh_to_najia_v1",
                    coins_kind="synthetic_line_encoding_not_coin_tosses", parameters=details,
                    note="传统年月日时起卦后按六爻纳甲解读；六组仅为兼容计算器的爻态编码，并非投币结果。")
    elif method == "time_seed":
        coins = time_seed_coins(stamp)
        meta.update(algorithm="liuyao-time-seed-v1-sha256-first18-msb",
                    coins_kind="time_seed_simulated_coin_faces", seed_timestamp=stamp,
                    note="自定义确定性时间种子法，不是传统年月日时法；相同规范时间得到相同六组。")
    else:
        coins = random_coins()
        meta.update(algorithm="secrets-randbits-18-v1", coins_kind="program_simulated_coin_faces",
                    note="程序独立生成18个公平币面，每三位组成一爻。")
    meta["raw_coins"] = list(coins)
    result = najia.build_output({**base, "coins": coins})
    return {"status": "ready", "casting": meta, **result}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="-", help="JSON file or - for stdin")
    parser.add_argument("--output", default="-", help="JSON file or - for stdout")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.input != "-" and args.output != "-" and Path(args.input).resolve() == Path(args.output).resolve():
        raise SystemExit("Input and output paths must differ")
    try:
        raw = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
        result, code = build_output(json.loads(raw)), 0
    except Exception as exc:
        result, code = {"error": type(exc).__name__, "message": str(exc)}, 2
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output == "-":
        sys.stdout.write(text)
    else:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
    return code

if __name__ == "__main__":
    raise SystemExit(main())
