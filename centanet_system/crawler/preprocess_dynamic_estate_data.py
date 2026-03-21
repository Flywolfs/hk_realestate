"""
预处理脚本：从交易记录目录预计算每个小区的面积范围和当前尺价
输出：dynamic_estate_data.json

用法：
    python3 preprocess_dynamic_estate_data.py <transaction_buy_dir> [output_path]

示例：
    python3 preprocess_dynamic_estate_data.py transaction_record_20260314_trans/buy
    python3 preprocess_dynamic_estate_data.py transaction_record_20260314_trans/buy ./dynamic_estate_data.json
"""

import json
import os
import sys


def compute_estate_stats(transaction_buy_dir: str) -> dict:
    """
    遍历 buy 目录下所有 JSON 文件，预计算每个小区的面积范围和当前尺价。

    :param transaction_buy_dir: 交易记录 buy 目录路径
    :return: {estate_id: {min_area, max_area, current_price_per_sqft}}
    """
    result = {}

    if not os.path.isdir(transaction_buy_dir):
        print(f"错误: 目录不存在 {transaction_buy_dir}")
        sys.exit(1)

    files = [f for f in os.listdir(transaction_buy_dir) if f.endswith('.json')]
    total = len(files)
    print(f"共找到 {total} 个交易记录文件，开始预处理...")

    for i, filename in enumerate(files, 1):
        estate_id = filename[:-5]  # 去掉 .json 后缀
        filepath = os.path.join(transaction_buy_dir, filename)

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"警告: 解析失败 {filename}: {e}")
            continue

        transactions = data.get('transactions', [])
        if not transactions:
            continue

        # ---- 面积范围 ----
        areas = []
        for trans in transactions:
            area = trans.get('saleable_area') or trans.get('area')
            if area and isinstance(area, (int, float)) and area > 0:
                areas.append(area)

        # ---- 当前尺价（最近5条的均值）----
        recent_trans = transactions[:5]
        prices = []
        for trans in recent_trans:
            price = trans.get('price_per_sqft')
            if price and isinstance(price, (int, float)) and price > 0:
                prices.append(price)

        entry = {}
        if areas:
            entry['min_area'] = min(areas)
            entry['max_area'] = max(areas)
        if prices:
            entry['current_price_per_sqft'] = round(sum(prices) / len(prices), 2)

        if entry:
            result[estate_id] = entry

        if i % 500 == 0 or i == total:
            print(f"  进度: {i}/{total}")

    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    transaction_buy_dir = sys.argv[1]

    # 输出路径默认与脚本同目录
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, 'dynamic_estate_data.json')

    result = compute_estate_stats(transaction_buy_dir)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n预处理完成，共 {len(result)} 个小区")
    print(f"输出文件: {output_path}")


if __name__ == '__main__':
    main()
