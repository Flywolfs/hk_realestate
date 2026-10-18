#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计算屋苑买卖/租赁价格的年度变化走势（细分到户型）

功能：
1. 合并两个数据源，以 --cutoff-date（默认 2025-01-01）为分界，避免重复统计：
   - 分界日期之前的记录：取自历史目录 --history-dir
     （默认 all/transaction_record_all_history，2026-08-23 爬取的全部历史成交）
   - 分界日期之后的记录：取自近期目录 --recent-dir
     （默认 transaction_record_20261018，2025-01-01 至爬取日的成交，可配置以便后续重算）
   - 若某个屋苑只存在于其中一个目录，则回退使用该目录的全量记录，避免丢数据
2. 按户型分组（与 calculate_rent_sale_ratio.py 的做法一致）：
   - bedroomCount > 0 的记录直接按房间数分组（2房、3房...）
   - bedroomCount 缺失或为 0 的记录按面积聚类，容差 8%
3. 计算每个屋苑整体及每个户型的年度单价走势：
   - series：每年平均单价（每年先按 IQR 剔除异常值）与样本数
   - yoy：相对上一个有数据年份的涨跌幅（%）
   - total_change_pct / cagr_pct：最早年份到最新年份的累计涨跌幅与年化涨跌幅
4. 输出 JSON（默认 annual_price_trend.json），字段说明详见 calculate_annual_price_trend_README.md

字段说明：
   - 买卖单价（psf）：直接取 nUnitPrice（港元/平方呎），缺失时用 transactionPrice / nArea 补齐
   - 租赁单价（psf）：transactionPrice / nArea（月租/平方呎）
   - 成交日期：max(regDate, insDate)，租赁记录通常没有 regDate，只取 insDate

用法示例：
    # 默认：历史目录 all/transaction_record_all_history + 近期目录 transaction_record_20261018
    python3 -u calculate_annual_price_trend.py

    # 后续重算：只需指定新的近期目录
    python3 -u calculate_annual_price_trend.py --recent-dir ./transaction_record_20261101

    # 调试：只处理指定屋苑
    python3 -u calculate_annual_price_trend.py --estate-ids 2-AAPPWPPEPK,2-ABBEGPWXPP
"""

import argparse
import json
import logging
import os
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_HISTORY_DIR = SCRIPT_DIR / "all" / "transaction_record_all_history"
DEFAULT_RECENT_DIR = SCRIPT_DIR / "transaction_record_20261018"
DEFAULT_OUTPUT = SCRIPT_DIR / "annual_price_trend.json"
DEFAULT_CUTOFF_DATE = "2025-01-01"

AREA_TOLERANCE = 0.08  # 面积聚类容差（8%，与 calculate_rent_sale_ratio.py 一致）
IQR_MIN_SAMPLES = 4    # 样本量小于该值时不剔除异常值

logger = logging.getLogger(__name__)


def setup_logging(level: int = logging.INFO) -> None:
    """配置日志（含文件名和行号，实时输出）"""
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


# --------------------------------------------------------------------------- #
# 原始数据解析                                                                  #
# --------------------------------------------------------------------------- #
def parse_transaction_date(item: Dict) -> Optional[datetime.date]:
    """成交日期取 max(regDate, insDate)（与 transfer_transcation_data.py 一致）"""
    dates = []
    for field in ("regDate", "insDate"):
        raw = item.get(field)
        if not raw:
            continue
        try:
            dates.append(datetime.strptime(str(raw)[:10], "%Y-%m-%d").date())
        except (ValueError, TypeError):
            continue
    return max(dates) if dates else None


def to_positive_float(value) -> Optional[float]:
    """转换为正数，无效值返回 None"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def is_true_flag(flag) -> bool:
    """中原 specialCase 形如 {"value": true, "remark": "..."} 或 {"value": false}"""
    if isinstance(flag, dict):
        return bool(flag.get("value"))
    return bool(flag)


def normalize_records(
    payload: Dict,
    kind: str,
    include_special_cases: bool = False,
    exclude_first_hand: bool = False,
) -> List[Dict]:
    """
    将中原原始成交记录转换为统一结构

    Args:
        payload: 原始 JSON（含 data 列表）
        kind: "sale" 或 "rent"
        include_special_cases: 是否保留特殊成交个案
        exclude_first_hand: 是否剔除一手成交（买卖）

    Returns:
        [{"id", "date", "psf", "area", "room_count"}, ...]
    """
    records = []
    for item in payload.get("data") or []:
        if not include_special_cases and is_true_flag(item.get("specialCase")):
            continue
        if exclude_first_hand and item.get("firstOrSecondHand") == "FirstHand":
            continue

        trans_date = parse_transaction_date(item)
        if trans_date is None:
            continue

        area = to_positive_float(item.get("nArea"))
        total_price = to_positive_float(item.get("transactionPrice"))

        if kind == "sale":
            psf = to_positive_float(item.get("nUnitPrice"))
            if psf is None and total_price is not None and area is not None:
                psf = total_price / area
        else:
            psf = total_price / area if (total_price is not None and area is not None) else None
            if psf is None:
                psf = to_positive_float(item.get("nUnitPrice"))

        if psf is None:
            continue

        room_count = item.get("bedroomCount")
        try:
            room_count = int(room_count) if room_count is not None else None
        except (TypeError, ValueError):
            room_count = None
        if room_count is not None and room_count <= 0:
            room_count = None

        records.append({
            "id": item.get("id") or "",
            "date": trans_date,
            "psf": psf,
            "area": area,
            "room_count": room_count,
        })

    return records


def load_source_file(path: Path, kind: str, options: Dict) -> Tuple[List[Dict], Optional[str]]:
    """读取单个原始成交文件，返回 (记录列表, 屋苑名)"""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    records = normalize_records(
        payload,
        kind,
        include_special_cases=options["include_special_cases"],
        exclude_first_hand=options["exclude_first_hand"],
    )

    estate_name = None
    for item in payload.get("data") or []:
        if item.get("estateName"):
            estate_name = item["estateName"]
            break

    return records, estate_name


def load_estate_records(estate_id: str, kind: str, options: Dict) -> Tuple[List[Dict], Optional[str]]:
    """
    按分界日期合并历史目录与近期目录中同一屋苑的记录

    - 分界日期之前：历史目录
    - 分界日期之后：近期目录
    - 某目录缺失该屋苑文件时，回退使用另一目录的全量记录
    - 按记录 id 去重，防止同一笔成交被重复统计
    """
    history_file = Path(options["history_dir"]) / kind / f"{estate_id}.json"
    recent_file = Path(options["recent_dir"]) / kind / f"{estate_id}.json"
    cutoff = datetime.strptime(options["cutoff_date"], "%Y-%m-%d").date()

    merged: List[Dict] = []
    seen = set()
    estate_name = None

    def absorb(path: Path, keep) -> None:
        nonlocal estate_name
        records, name = load_source_file(path, kind, options)
        if estate_name is None and name:
            estate_name = name
        for record in records:
            if not keep(record["date"]):
                continue
            dedup_key = record["id"] or (record["date"], record["psf"], record["area"])
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            merged.append(record)

    has_history = history_file.exists()
    has_recent = recent_file.exists()
    if has_history:
        # 近期目录没有该屋苑时，历史目录中的数据全部使用
        absorb(history_file, (lambda d: True) if not has_recent else (lambda d: d < cutoff))
    if has_recent:
        # 历史目录没有该屋苑时，近期目录中的数据全部使用（含分界日期之前的记录）
        absorb(recent_file, (lambda d: d >= cutoff) if has_history else (lambda d: True))

    return merged, estate_name


# --------------------------------------------------------------------------- #
# 户型分组                                                                      #
# --------------------------------------------------------------------------- #
def _avg_area(group: Dict) -> Optional[float]:
    """聚类当前的平均面积"""
    if group["area_count"] == 0:
        return None
    return group["area_sum"] / group["area_count"]


def _append_to_group(group: Dict, record: Dict) -> None:
    group["records"].append(record)
    if record["area"]:
        group["area_sum"] += record["area"]
        group["area_count"] += 1


def _unique_key(base_key: str, used_keys: set) -> str:
    """保证输出 key 唯一"""
    key = base_key
    suffix = 2
    while key in used_keys:
        key = f"{base_key}_{suffix}"
        suffix += 1
    used_keys.add(key)
    return key


def build_room_groups(records: List[Dict]) -> List[Tuple[str, Dict, List[Dict]]]:
    """
    按户型分组（与 calculate_rent_sale_ratio.py 的做法一致）

    - room_count > 0 的记录按房间数分组
    - room_count 缺失的记录按面积聚类（容差 8%，优先并入最接近的已有分组）
    - 面积也缺失且无房间数的记录不参与户型分析（仍计入整体）

    Returns:
        [(分组key, 分组信息, 分组内记录), ...]，按平均面积升序
    """
    room_groups: Dict[int, Dict] = {}
    area_groups: List[Dict] = []

    # 先按房间数分组（与记录顺序无关）
    for record in records:
        if record["room_count"]:
            group = room_groups.setdefault(
                record["room_count"],
                {"records": [], "area_sum": 0.0, "area_count": 0},
            )
            _append_to_group(group, record)

    # 无房间数的记录按面积升序聚类，保证结果与原始记录顺序无关
    no_room_records = sorted(
        (r for r in records if not r["room_count"] and r["area"]),
        key=lambda r: r["area"],
    )
    for record in no_room_records:
        best_group = None
        best_diff = AREA_TOLERANCE
        for group in list(room_groups.values()) + area_groups:
            avg_area = _avg_area(group)
            if avg_area is None:
                continue
            diff = abs(record["area"] - avg_area) / avg_area
            if diff < best_diff:
                best_group, best_diff = group, diff

        if best_group is None:
            best_group = {"records": [], "area_sum": 0.0, "area_count": 0}
            area_groups.append(best_group)

        _append_to_group(best_group, record)

    grouped: List[Tuple[str, Dict, List[Dict]]] = []
    used_keys = set()

    for room_count, group in room_groups.items():
        avg_area = _avg_area(group)
        meta = {
            "bedroom_count": room_count,
            "avg_area": int(round(avg_area)) if avg_area else None,
            "group_method": "room_count",
            "sample_count": len(group["records"]),
        }
        grouped.append((_unique_key(f"{room_count}房", used_keys), meta, group["records"]))

    for group in area_groups:
        avg_area = _avg_area(group)
        meta = {
            "bedroom_count": None,
            "avg_area": int(round(avg_area)) if avg_area else None,
            "group_method": "area_cluster",
            "sample_count": len(group["records"]),
        }
        grouped.append((_unique_key(f"{int(round(avg_area))}呎", used_keys), meta, group["records"]))

    grouped.sort(key=lambda item: (item[1]["avg_area"] is None, item[1]["avg_area"] or 0))
    return grouped


# --------------------------------------------------------------------------- #
# 年度走势计算                                                                  #
# --------------------------------------------------------------------------- #
def remove_outliers_iqr(values: List[float]) -> List[float]:
    """IQR 剔除异常值（样本量不足时原样返回）"""
    if len(values) < IQR_MIN_SAMPLES:
        return values

    arr = np.asarray(values, dtype=float)
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    filtered = [v for v in values if lower_bound <= v <= upper_bound]
    return filtered or values


def build_yearly_series(records: List[Dict], min_samples: int) -> Dict[str, Dict]:
    """按年份聚合单价，返回 {年份: {"psf": 平均单价, "n": 样本数}}"""
    by_year: Dict[int, List[float]] = defaultdict(list)
    for record in records:
        by_year[record["date"].year].append(record["psf"])

    series = {}
    for year in sorted(by_year):
        raw_values = by_year[year]
        if len(raw_values) < min_samples:
            continue
        values = remove_outliers_iqr(raw_values)
        series[str(year)] = {
            "psf": round(float(np.mean(values)), 2),
            "n": len(raw_values),
        }
    return series


def build_trend(series: Dict[str, Dict]) -> Optional[Dict]:
    """
    基于年度序列生成走势

    Returns:
        {
          first_year/latest_year: 首末有数据的年份
          first_psf/latest_psf: 首末年份平均单价
          total_change_pct: 首末累计涨跌幅（%）
          cagr_pct: 首末年化涨跌幅（%）
          series: 年度单价序列
          yoy: {年份: {prev_year, pct}} 相对上一个有数据年份的涨跌幅
        }
    """
    years = sorted(series, key=int)
    if not years:
        return None

    yoy = {}
    for prev_year, cur_year in zip(years, years[1:]):
        prev_psf = series[prev_year]["psf"]
        cur_psf = series[cur_year]["psf"]
        if prev_psf <= 0:
            continue
        gap = int(cur_year) - int(prev_year)
        entry = {
            "prev_year": prev_year,
            "years_gap": gap,
            "pct": round((cur_psf - prev_psf) / prev_psf * 100, 2),
        }
        if gap > 1:
            # 中间年份缺数据时，额外给出年化涨跌幅
            entry["annualized_pct"] = round(((cur_psf / prev_psf) ** (1.0 / gap) - 1) * 100, 2)
        yoy[cur_year] = entry

    first_year, latest_year = years[0], years[-1]
    first_psf = series[first_year]["psf"]
    latest_psf = series[latest_year]["psf"]
    year_gap = int(latest_year) - int(first_year)

    total_change_pct = None
    cagr_pct = None
    if year_gap > 0 and first_psf > 0:
        ratio = latest_psf / first_psf
        total_change_pct = round((ratio - 1) * 100, 2)
        cagr_pct = round((ratio ** (1.0 / year_gap) - 1) * 100, 2)

    return {
        "first_year": first_year,
        "latest_year": latest_year,
        "first_psf": first_psf,
        "latest_psf": latest_psf,
        "total_change_pct": total_change_pct,
        "cagr_pct": cagr_pct,
        "series": series,
        "yoy": yoy,
    }


# --------------------------------------------------------------------------- #
# 单屋苑处理                                                                    #
# --------------------------------------------------------------------------- #
def process_estate(estate_id: str, options: Dict) -> Tuple[str, Optional[Dict]]:
    """处理单个屋苑的买卖与租赁数据，返回 (estate_id, 结果)"""
    result: Dict = {}
    estate_name = None

    for kind in ("sale", "rent"):
        records, name = load_estate_records(estate_id, kind, options)
        if estate_name is None and name:
            estate_name = name
        if not records:
            continue

        overall = build_trend(build_yearly_series(records, options["min_samples"]))
        if overall is None:
            continue

        room_types = {}
        for key, meta, group_records in build_room_groups(records):
            if len(group_records) < options["min_group_samples"]:
                continue
            trend = build_trend(build_yearly_series(group_records, options["min_samples"]))
            if trend is None:
                continue
            room_types[key] = {**meta, **trend}

        result[kind] = {
            "overall": overall,
            "room_types": room_types,
        }

    if not result:
        return estate_id, None

    return estate_id, {"estate_name": estate_name, **result}


def process_estate_task(task: Tuple[str, Dict]) -> Tuple[str, Optional[Dict], Optional[str]]:
    """多进程任务包装，返回 (estate_id, 结果, 错误信息)"""
    estate_id, options = task
    try:
        estate_id, data = process_estate(estate_id, options)
        return estate_id, data, None
    except Exception as exc:  # noqa: BLE001
        return estate_id, None, f"{type(exc).__name__}: {exc}"


# --------------------------------------------------------------------------- #
# 主流程                                                                        #
# --------------------------------------------------------------------------- #
def collect_estate_ids(history_dir: Path, recent_dir: Path) -> List[str]:
    """收集两个目录中所有的屋苑 ID"""
    estate_ids = set()
    for base in (history_dir, recent_dir):
        for kind in ("sale", "rent"):
            folder = base / kind
            if not folder.is_dir():
                continue
            for entry in folder.iterdir():
                if entry.suffix == ".json":
                    estate_ids.add(entry.stem)
    return sorted(estate_ids)


def save_results(results: Dict, output_path: Path, metadata: Dict) -> None:
    """原子写入结果 JSON"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(output_path.parent), prefix=f"{output_path.name}.", suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump({"metadata": metadata, "data": results}, f, ensure_ascii=False, indent=2)
        os.chmod(tmp_name, 0o644)
        os.replace(tmp_name, output_path)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="计算屋苑买卖/租赁价格的年度变化走势（细分到户型）")
    parser.add_argument(
        "--history-dir", default=str(DEFAULT_HISTORY_DIR),
        help="历史数据目录（分界日期之前的记录来源）")
    parser.add_argument(
        "--recent-dir", default=str(DEFAULT_RECENT_DIR),
        help="近期数据目录（分界日期之后的记录来源，后续重算时指向最新爬取目录）")
    parser.add_argument(
        "--cutoff-date", default=DEFAULT_CUTOFF_DATE,
        help="两个数据源的分界日期（默认 2025-01-01）")
    parser.add_argument(
        "--output", default=str(DEFAULT_OUTPUT),
        help="输出 JSON 路径（默认 annual_price_trend.json）")
    parser.add_argument(
        "--min-samples", type=int, default=1,
        help="每年最少样本数，低于该值的年份不参与走势计算（默认 1，可调高降噪）")
    parser.add_argument(
        "--min-group-samples", type=int, default=3,
        help="户型分组最少样本数，低于该值的分组不输出（默认 3）")
    parser.add_argument(
        "--workers", type=int, default=min(8, os.cpu_count() or 1),
        help="并行进程数（默认 min(8, CPU核数)）")
    parser.add_argument(
        "--include-special-cases", action="store_true",
        help="保留特殊成交个案（默认剔除）")
    parser.add_argument(
        "--exclude-first-hand", action="store_true",
        help="剔除一手成交（默认保留）")
    parser.add_argument(
        "--estate-ids", default=None,
        help="只处理指定屋苑 ID（逗号分隔，调试用）")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    setup_logging()
    args = parse_args(argv)

    history_dir = Path(args.history_dir).resolve()
    recent_dir = Path(args.recent_dir).resolve()
    output_path = Path(args.output)

    logger.info("=" * 60)
    logger.info("开始计算屋苑年度价格走势（分户型）")
    logger.info("=" * 60)
    logger.info(f"历史数据目录: {history_dir}")
    logger.info(f"近期数据目录: {recent_dir}")
    logger.info(f"分界日期: {args.cutoff_date}（之前取历史目录，之后取近期目录）")

    try:
        cutoff_date = datetime.strptime(args.cutoff_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error(f"无效的分界日期: {args.cutoff_date}，格式应为 YYYY-MM-DD")
        return 1

    for folder in (history_dir, recent_dir):
        if not folder.is_dir():
            logger.error(f"数据目录不存在: {folder}")
            return 1

    if args.workers < 1:
        logger.error("--workers 必须 >= 1")
        return 1
    if args.min_samples < 1 or args.min_group_samples < 1:
        logger.error("--min-samples 与 --min-group-samples 必须 >= 1")
        return 1

    estate_ids = collect_estate_ids(history_dir, recent_dir)
    if args.estate_ids:
        wanted = {item.strip() for item in args.estate_ids.split(",") if item.strip()}
        estate_ids = [eid for eid in estate_ids if eid in wanted]
        logger.info(f"按 --estate-ids 过滤后屋苑数: {len(estate_ids)}")

    if not estate_ids:
        logger.error("未找到任何屋苑数据文件")
        return 1

    logger.info(f"待处理屋苑数: {len(estate_ids)}")

    options = {
        "history_dir": str(history_dir),
        "recent_dir": str(recent_dir),
        "cutoff_date": cutoff_date.strftime("%Y-%m-%d"),
        "min_samples": args.min_samples,
        "min_group_samples": args.min_group_samples,
        "include_special_cases": args.include_special_cases,
        "exclude_first_hand": args.exclude_first_hand,
    }

    results: Dict[str, Dict] = {}
    failed = 0
    processed = 0
    started_at = datetime.now()

    if args.workers == 1:
        for estate_id in estate_ids:
            eid, data, error = process_estate_task((estate_id, options))
            if error:
                failed += 1
                logger.error(f"处理屋苑 {eid} 失败: {error}")
            elif data:
                results[eid] = data
            processed += 1
            if processed % 200 == 0 or processed == len(estate_ids):
                elapsed = (datetime.now() - started_at).total_seconds()
                logger.info(
                    f"进度: {processed}/{len(estate_ids)}，已生成 {len(results)} 个屋苑，"
                    f"失败 {failed}，耗时 {elapsed:.1f}s")
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(process_estate_task, (eid, options)) for eid in estate_ids]
            for future in as_completed(futures):
                eid, data, error = future.result()
                if error:
                    failed += 1
                    logger.error(f"处理屋苑 {eid} 失败: {error}")
                elif data:
                    results[eid] = data
                processed += 1
                if processed % 200 == 0 or processed == len(estate_ids):
                    elapsed = (datetime.now() - started_at).total_seconds()
                    logger.info(
                        f"进度: {processed}/{len(estate_ids)}，已生成 {len(results)} 个屋苑，"
                        f"失败 {failed}，耗时 {elapsed:.1f}s")

    sorted_results = {eid: results[eid] for eid in sorted(results)}

    total_room_groups = sum(
        len(section.get("room_types", {}))
        for data in sorted_results.values()
        for section in (data.get("sale"), data.get("rent"))
        if section
    )
    sale_estates = sum(1 for data in sorted_results.values() if data.get("sale"))
    rent_estates = sum(1 for data in sorted_results.values() if data.get("rent"))

    metadata = {
        "description": "屋苑买卖/租赁价格年度变化走势（整体 + 分户型）",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "history_dir": str(history_dir),
        "recent_dir": str(recent_dir),
        "cutoff_date": options["cutoff_date"],
        "total_estates": len(sorted_results),
        "sale_estates": sale_estates,
        "rent_estates": rent_estates,
        "total_room_type_groups": total_room_groups,
        "price_unit": "港元/平方呎",
        "sale_price_field": "nUnitPrice（缺失时用 transactionPrice / nArea 补齐）",
        "rent_price_field": "transactionPrice / nArea（月租/平方呎）",
        "date_rule": "max(regDate, insDate)；租赁记录仅有 insDate",
        "merge_rule": (
            f"日期 < {options['cutoff_date']} 的记录取自 history_dir，"
            f"日期 >= {options['cutoff_date']} 的记录取自 recent_dir；"
            "某目录缺少该屋苑文件时回退使用另一目录；按记录 id 去重"
        ),
        "clustering_method": (
            "bedroomCount > 0 按房间数分组；缺失或为 0 时按面积聚类（容差 8%）；"
            "key 形如 '2房' 或 '450呎'"
        ),
        "outlier_removal": f"每个户型每年做 IQR(1.5) 剔除，样本量 < {IQR_MIN_SAMPLES} 时不做剔除",
        "min_samples_per_year": options["min_samples"],
        "min_group_samples": options["min_group_samples"],
        "excluded_special_cases": not options["include_special_cases"],
        "excluded_first_hand": options["exclude_first_hand"],
        "fields": {
            "series": "按年份的平均单价与样本数，{年份: {psf, n}}",
            "yoy": (
                "相对上一个有数据年份的涨跌幅，{年份: {prev_year, years_gap, pct}}；"
                "years_gap 为相距年数，大于 1 时额外提供 annualized_pct（年化涨跌幅）"
            ),
            "total_change_pct": "最早年份到最新年份的累计涨跌幅（%）；只有 1 个年份有数据时为 null",
            "cagr_pct": "最早年份到最新年份的年化涨跌幅（%）；只有 1 个年份有数据时为 null",
        },
    }

    save_results(sorted_results, output_path, metadata)

    elapsed = (datetime.now() - started_at).total_seconds()
    logger.info("=" * 60)
    logger.info(f"处理完成: {len(sorted_results)} 个屋苑（买卖 {sale_estates}，租赁 {rent_estates}），"
                f"户型分组 {total_room_groups} 个，失败 {failed}，耗时 {elapsed:.1f}s")
    logger.info(f"结果已保存到: {output_path}")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
