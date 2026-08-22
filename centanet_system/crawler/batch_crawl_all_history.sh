#!/usr/bin/env bash
# ============================================================
# 分批全量历史成交记录爬取脚本
#
# 原理：
#   每批通过 --start-from + --max-estates 定位一批屋苑，
#   用 --all-history 爬取该批屋苑的【全部历史】成交记录。
#   所有批次输出到同一目录，每个屋苑的JSON文件都是独立完整的
#   全量数据，全部跑完后目录即为完整数据（无需额外合并步骤）。
#
# 断点续爬：
#   任意批次中断后，重新运行本脚本即可。已完成的屋苑会被
#   --skip-existing-files 自动跳过（该屋苑的JSON文件已存在即视为完成），
#   只会继续爬未完成的屋苑，不会重复请求。
#
# 用法：
#   bash batch_crawl_all_history.sh
#   或先 chmod +x batch_crawl_all_history.sh 再 ./batch_crawl_all_history.sh
# ============================================================
set -u
cd "$(dirname "$0")"

# ====== 可配置参数 ======
ESTATE_INFO="estate_info_20260221.json"      # 屋苑信息文件
OUTPUT_DIR="transaction_record_all_history"  # 输出目录（所有批次共用）
BATCH_SIZE=2000                              # 每批屋苑数量
TOTAL_ESTATES=10000                          # 屋苑总数
WORKERS=5                                    # 并发线程数
INTERVAL=1.5                                 # 请求间隔（秒）
# =========================

echo "分批全量爬取配置:"
echo "  屋苑信息: $ESTATE_INFO"
echo "  输出目录: $OUTPUT_DIR"
echo "  每批数量: $BATCH_SIZE, 总屋苑: $TOTAL_ESTATES, 批次数: $(( (TOTAL_ESTATES + BATCH_SIZE - 1) / BATCH_SIZE ))"
echo "  并发: $WORKERS 线程, 间隔: ${INTERVAL}s"

for ((start = 0; start < TOTAL_ESTATES; start += BATCH_SIZE)); do
    end=$((start + BATCH_SIZE - 1))
    if [ "$end" -ge "$((TOTAL_ESTATES - 1))" ]; then
        end=$((TOTAL_ESTATES - 1))
    fi
    echo ""
    echo "=============================================="
    echo "  批次: 屋苑 $start ~ $end (共 $((end - start + 1)) 个)"
    echo "=============================================="
    python3 -u scrape_centanet_transactions.py \
        --estate-info "$ESTATE_INFO" \
        --all-history \
        --output-dir "$OUTPUT_DIR" \
        --start-from "$start" \
        --max-estates "$BATCH_SIZE" \
        --skip-existing-files \
        --skip-empty-file empty_estate.txt \
        --workers "$WORKERS" \
        --interval "$INTERVAL"
done

echo ""
echo "全部批次完成！完整数据已输出到: $OUTPUT_DIR"
