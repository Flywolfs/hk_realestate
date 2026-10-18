# annual_price_trend.json 数据结构说明

本文档说明 `calculate_annual_price_trend.py` 生成的 `annual_price_trend.json` 的格式与字段含义。

- 生成脚本：`centanet_system/crawler/calculate_annual_price_trend.py`
- 输出文件：`centanet_system/crawler/annual_price_trend.json`
- 内容：每个屋苑的**买卖 / 租赁价格年度走势**（整体 + 细分到户型）
- 价格单位：**港元/平方呎**（买卖为成交单价，租赁为月租/平方呎）
- 涨跌幅单位：**百分比（%）**，例如 `16.72` 表示上涨 16.72%

当前生成结果（2026-10-18）：

| 指标 | 数值 |
| --- | --- |
| 屋苑总数 | 5828 |
| 有买卖走势的屋苑 | 5701 |
| 有租赁走势的屋苑 | 3038 |
| 户型分组总数 | 15439 |

> 未出现在 `data` 中的屋苑：所有成交记录都缺少面积/单价（无法计算每呎价格），或记录全部被过滤，因此无法生成走势。

---

## 1. 顶层结构

```json
{
  "metadata": { ... },          // 本次计算的元信息（数据源、口径、开关）
  "data": {                     // 以屋苑 ID 为 key
    "2-AEBKPPSJPK": { ... },
    "2-ABBEGPWXPP": { ... }
  }
}
```

- `metadata`：对象，描述数据来源与计算口径，不含业务数据。
- `data`：对象，key 为中原屋苑 ID（即原始文件名去掉 `.json`，如 `2-AEBKPPSJPK`），value 为该屋苑的走势数据。

---

## 2. metadata 字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `description` | string | 固定描述文本 |
| `generated_at` | string | 生成时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `history_dir` | string | 历史数据目录（分界日期之前的记录来源） |
| `recent_dir` | string | 近期数据目录（分界日期之后的记录来源，后续重算时替换该目录） |
| `cutoff_date` | string | 两个数据源的分界日期，默认 `2025-01-01` |
| `total_estates` | int | `data` 中的屋苑数量 |
| `sale_estates` | int | 有买卖走势的屋苑数量 |
| `rent_estates` | int | 有租赁走势的屋苑数量 |
| `total_room_type_groups` | int | 所有屋苑的户型分组数量合计（买卖 + 租赁） |
| `price_unit` | string | 价格单位：`港元/平方呎` |
| `sale_price_field` | string | 买卖单价取值规则：`nUnitPrice`，缺失时用 `transactionPrice / nArea` 补齐 |
| `rent_price_field` | string | 租赁单价取值规则：`transactionPrice / nArea` |
| `date_rule` | string | 成交日期规则：`max(regDate, insDate)`，租赁通常只有 `insDate` |
| `merge_rule` | string | 双数据源合并规则（分界日期、回退、去重） |
| `clustering_method` | string | 户型分组规则 |
| `outlier_removal` | string | 异常值剔除规则：每个户型每年做 IQR(1.5)，样本 < 4 时不剔除 |
| `min_samples_per_year` | int | 每年最少样本数；低于该值的年份不进入 `series`（默认 1） |
| `min_group_samples` | int | 户型分组最少总样本数；低于该值的分组不输出（默认 3） |
| `excluded_special_cases` | bool | 是否剔除「特殊成交个案」（默认 true，即已剔除） |
| `excluded_first_hand` | bool | 是否剔除一手成交（默认 false，即保留） |
| `fields` | object | 对各字段的业务解释，便于下游读取时自描述 |

---

## 3. data 下单个屋苑的结构

```json
"2-AEBKPPSJPK": {
  "estate_name": "綠楊新邨",
  "sale": { "overall": {...}, "room_types": {...} },
  "rent": { "overall": {...}, "room_types": {...} }
}
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `estate_name` | string \| null | 屋苑名称（取自中原成交记录中的 `estateName`） |
| `sale` | object \| 无 | 买卖走势。若该屋苑没有任何可计算的买卖记录，则该 key 不存在 |
| `rent` | object \| 无 | 租赁走势。若该屋苑没有任何可计算的租赁记录，则该 key 不存在 |

`sale` / `rent` 对象内部结构完全一致：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `overall` | object | 整个屋苑（不分户型）的年度走势 |
| `room_types` | object | 分户型走势，key 为户型名称，value 为走势对象 |

---

## 4. 走势对象（overall 与每个户型分组）

走势对象 = **汇总字段 + `series`（年度序列） + `yoy`（年度涨跌幅）**。

### 4.1 汇总字段

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `first_year` | string | `series` 中最早有数据的年份，如 `"1995"` |
| `latest_year` | string | `series` 中最晚有数据的年份，如 `"2026"` |
| `first_psf` | float | 最早年份的平均单价（港元/平方呎） |
| `latest_psf` | float | 最新年份的平均单价（港元/平方呎） |
| `total_change_pct` | float \| null | 从最早年份到最新年份的**累计涨跌幅（%）**；只有 1 个年份有数据时为 `null` |
| `cagr_pct` | float \| null | 从最早年份到最新年份的**年化涨跌幅（CAGR，%）**；只有 1 个年份有数据时为 `null` |

计算公式：

```
total_change_pct = (latest_psf / first_psf - 1) * 100
cagr_pct         = ((latest_psf / first_psf) ^ (1 / (latest_year - first_year)) - 1) * 100
```

### 4.2 `series`：年度单价序列

```json
"series": {
  "1995": { "psf": 4109.62, "n": 5 },
  "1996": { "psf": 4321.10, "n": 8 }
}
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| key | string | 年份（`YYYY`），按时间升序排列 |
| `psf` | float | 该年份的平均单价（港元/平方呎）。计算前先对该年样本做 IQR(1.5) 剔除异常值，再取均值 |
| `n` | int | 该年份的**原始成交样本数**（剔除异常值之前的条数，用于判断数据可信度） |

> 只有该年有效样本数 ≥ `metadata.min_samples_per_year`（默认 1）的年份才会出现在 `series` 中。

### 4.3 `yoy`：年度涨跌幅

```json
"yoy": {
  "2024": { "prev_year": "2023", "years_gap": 1, "pct": -5.23 },
  "2026": { "prev_year": "2023", "years_gap": 3, "pct": 8.10, "annualized_pct": 2.63 }
}
```

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| key | string | 当前年份（`YYYY`） |
| `prev_year` | string | 与之比较的**上一个有数据的年份**（不一定是上一年，中间可能缺数据） |
| `years_gap` | int | 与 `prev_year` 相距的年数 |
| `pct` | float | 相对 `prev_year` 的涨跌幅（%）。`years_gap > 1` 时这是**区间累计**涨跌幅 |
| `annualized_pct` | float \| 无 | 仅当 `years_gap > 1` 时出现，表示区间年化涨跌幅（%） |

计算公式：

```
pct            = (当年 psf / 上一年份 psf - 1) * 100
annualized_pct = ((当年 psf / 上一年份 psf) ^ (1 / years_gap) - 1) * 100
```

> 注意：`yoy` 是「年变化幅度」的核心字段。若某年因样本不足被跳过，`yoy` 会跨年比较，此时请优先看 `years_gap` 和 `annualized_pct`。

### 4.4 户型分组额外字段（`room_types` 下的每个 value）

`room_types` 的 key 是户型名称：

- 按房间数分组：`"1房"`、`"2房"`、`"3房"` …（记录有 `bedroomCount` 时）
- 按面积聚类：`"450呎"`、`"484呎"` …（记录缺少 `bedroomCount` 时，按 8% 面积容差聚类，key 为组内平均面积）
- key 冲突时追加后缀，如 `"450呎_2"`

每个户型对象的字段 = 走势对象全部字段（见 4.1~4.3） + 以下分组信息：

| 字段 | 类型 | 含义 |
| --- | --- | --- |
| `bedroom_count` | int \| null | 房间数；面积聚类得到的组为 `null` |
| `avg_area` | int \| null | 分组内成交单位的平均面积（平方呎，四舍五入）；组内记录都缺面积时为 `null` |
| `group_method` | string | 分组方式：`"room_count"`（按房间数）或 `"area_cluster"`（按面积聚类） |
| `sample_count` | int | 该分组参与计算的全部历史成交条数（所有年份合计） |
| `first_year` ~ `yoy` | - | 与该分组的年度序列、涨跌幅，含义同 4.1~4.3 |

---

## 5. 完整示例（节选：綠楊新邨）

```json
"2-AEBKPPSJPK": {
  "estate_name": "綠楊新邨",
  "sale": {
    "overall": {
      "first_year": "1995",
      "latest_year": "2026",
      "first_psf": 4109.62,
      "latest_psf": 12993.07,
      "total_change_pct": 216.16,
      "cagr_pct": 3.78,
      "series": {
        "1995": { "psf": 4109.62, "n": 144 },
        "2024": { "psf": 11438.94, "n": 107 },
        "2025": { "psf": 11132.04, "n": 80 },
        "2026": { "psf": 12993.07, "n": 70 }
      },
      "yoy": {
        "2025": { "prev_year": "2024", "years_gap": 1, "pct": -2.68 },
        "2026": { "prev_year": "2025", "years_gap": 1, "pct": 16.72 }
      }
    },
    "room_types": {
      "2房": {
        "bedroom_count": 2,
        "avg_area": 452,
        "group_method": "room_count",
        "sample_count": 3751,
        "first_year": "1995",
        "latest_year": "2026",
        "first_psf": 4076.48,
        "latest_psf": 13282.13,
        "total_change_pct": 225.82,
        "cagr_pct": 3.88,
        "series": { "...": "..." },
        "yoy": { "2026": { "prev_year": "2025", "years_gap": 1, "pct": 14.43 } }
      },
      "3房": { "...": "..." }
    }
  },
  "rent": {
    "overall": {
      "first_year": "2021",
      "latest_year": "2026",
      "total_change_pct": 17.09,
      "cagr_pct": 3.21,
      "series": { "...": "..." },
      "yoy": { "...": "..." }
    },
    "room_types": {
      "2房": { "...": "..." },
      "3房": { "...": "..." }
    }
  }
}
```

> 该示例取自实际输出（`series`、`yoy` 为节选）。

---

## 6. 计算口径与数据来源

| 项目 | 规则 |
| --- | --- |
| 历史数据源 | `all/transaction_record_all_history`（2026-08-23 爬取的全部历史成交） |
| 近期数据源 | `transaction_record_20261018`（2025-01-01 至爬取日），可通过 `--recent-dir` 换成新目录 |
| 合并规则 | 日期 < 分界日期取历史数据源；日期 ≥ 分界日期取近期数据源；按记录 `id` 去重；某目录缺该屋苑时回退使用另一目录 |
| 成交日期 | `max(regDate, insDate)`；租赁记录一般只有 `insDate` |
| 买卖单价 | `nUnitPrice`，缺失时用 `transactionPrice / nArea` 补齐 |
| 租赁单价 | `transactionPrice / nArea`（月租/平方呎），面积缺失时退回 `nUnitPrice` |
| 异常值处理 | 每个户型每年独立做 IQR(1.5) 剔除；样本数 < 4 的年份不剔除 |
| 户型分组 | `bedroomCount > 0` 按房间数；缺失或为 0 时按面积聚类（容差 8%，优先并入最接近的已有分组） |
| 特殊成交 | 默认剔除 `specialCase.value = true` 的记录 |
| 一手成交 | 默认保留，可用 `--exclude-first-hand` 剔除 |
| 租赁历史范围 | 中原 API 仅提供 2021 年起的租赁记录，因此租赁走势最早从 2021 年开始 |

---

## 7. 读取示例

```python
import json

with open("centanet_system/crawler/annual_price_trend.json", encoding="utf-8") as f:
    trends = json.load(f)["data"]

estate = trends["2-AEBKPPSJPK"]

# 1) 屋苑整体：最新一年的售价涨跌幅
sale_all = estate["sale"]["overall"]
latest = sale_all["latest_year"]
print("整体最新年涨跌幅:", sale_all["yoy"].get(latest, {}).get("pct"))

# 2) 分户型：2房的最新一年售价涨跌幅
room_2 = estate["sale"]["room_types"]["2房"]
print("2房最新年涨跌幅:", room_2["yoy"].get(room_2["latest_year"], {}).get("pct"))

# 3) 全屋苑 2026 年售价同比排行（只看有 2026 数据的屋苑）
rows = []
for estate_id, item in trends.items():
    overall = (item.get("sale") or {}).get("overall")
    if not overall:
        continue
    yoy = overall["yoy"].get("2026")
    if yoy and yoy["years_gap"] == 1:
        rows.append((estate_id, item.get("estate_name"), yoy["pct"]))
rows.sort(key=lambda x: x[2], reverse=True)
print(rows[:10])
```

---

## 8. 重新生成

```bash
cd centanet_system/crawler

# 默认：历史目录 + transaction_record_20261018，分界日期 2025-01-01
/home/zhangchi/Documents/28hse/.venv/bin/python -u calculate_annual_price_trend.py

# 下次爬完新目录后重算（只需替换 --recent-dir）
/home/zhangchi/Documents/28hse/.venv/bin/python -u calculate_annual_price_trend.py \
  --recent-dir ./transaction_record_20261101 \
  --output ./annual_price_trend.json

# 降低噪声：要求每年至少 3 条成交才纳入序列
/home/zhangchi/Documents/28hse/.venv/bin/python -u calculate_annual_price_trend.py --min-samples 3
```

常用参数：

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--history-dir` | `all/transaction_record_all_history` | 历史数据目录 |
| `--recent-dir` | `transaction_record_20261018` | 近期数据目录（后续重算指向最新爬取目录） |
| `--cutoff-date` | `2025-01-01` | 两个数据源的分界日期 |
| `--output` | `annual_price_trend.json` | 输出 JSON 路径 |
| `--min-samples` | `1` | 每年最少样本数，低于该值的年份不进入 `series` |
| `--min-group-samples` | `3` | 户型分组最少总样本数 |
| `--workers` | `min(8, CPU核数)` | 并行进程数 |
| `--include-special-cases` | 关闭 | 保留特殊成交个案 |
| `--exclude-first-hand` | 关闭 | 剔除一手成交 |
| `--estate-ids` | 无 | 只处理指定屋苑（逗号分隔，调试用） |
