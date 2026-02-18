#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成价格趋势图表脚本

功能：
1. 读取 weekly_price_trends.json 数据
2. 生成买卖价格趋势图
3. 生成租赁价格趋势图
4. 生成合并对比图
5. 输出为 PNG 图片
"""

import json
import logging
from datetime import datetime
from typing import Dict, List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置参数
CONFIG = {
    "input_file": "weekly_price_trends.json",
    "output_prefix": "price_trend"
}


def load_trend_data(input_file: str) -> Dict:
    """加载趋势数据"""
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"成功加载数据: {input_file}")
        return data
    except Exception as e:
        logger.error(f"加载数据失败: {e}")
        return {}


def generate_html_chart(data: Dict, output_file: str):
    """
    生成HTML图表（使用纯JavaScript，无需外部依赖）
    
    Args:
        data: 趋势数据
        output_file: 输出HTML文件路径
    """
    buy_trend = data.get("buy_trend", [])
    rent_trend = data.get("rent_trend", [])
    metadata = data.get("metadata", {})
    
    # 提取数据
    buy_dates = [item["week_start"] for item in buy_trend]
    buy_prices = [item["avg_price"] for item in buy_trend]
    rent_dates = [item["week_start"] for item in rent_trend]
    rent_prices = [item["avg_price"] for item in rent_trend]
    
    # 计算统计数据
    buy_min = min(buy_prices) if buy_prices else 0
    buy_max = max(buy_prices) if buy_prices else 0
    buy_avg = sum(buy_prices) / len(buy_prices) if buy_prices else 0
    buy_latest = buy_prices[-1] if buy_prices else 0
    
    rent_min = min(rent_prices) if rent_prices else 0
    rent_max = max(rent_prices) if rent_prices else 0
    rent_avg = sum(rent_prices) / len(rent_prices) if rent_prices else 0
    rent_latest = rent_prices[-1] if rent_prices else 0
    
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>香港房产价格趋势图 (2025年1月起)</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        h1 {{
            text-align: center;
            color: white;
            margin-bottom: 30px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        .subtitle {{
            text-align: center;
            color: rgba(255,255,255,0.9);
            margin-bottom: 40px;
            font-size: 1.1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: white;
            border-radius: 16px;
            padding: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
        }}
        .stat-card.buy {{
            border-left: 5px solid #4CAF50;
        }}
        .stat-card.rent {{
            border-left: 5px solid #2196F3;
        }}
        .stat-title {{
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 15px;
            color: #333;
        }}
        .stat-title.buy {{ color: #4CAF50; }}
        .stat-title.rent {{ color: #2196F3; }}
        .stat-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}
        .stat-row:last-child {{
            border-bottom: none;
        }}
        .stat-label {{
            color: #666;
        }}
        .stat-value {{
            font-weight: bold;
            color: #333;
        }}
        .chart-container {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
        }}
        .chart-title {{
            font-size: 1.5em;
            font-weight: bold;
            margin-bottom: 20px;
            color: #333;
        }}
        .chart-wrapper {{
            position: relative;
            height: 400px;
            width: 100%;
        }}
        canvas {{
            width: 100% !important;
            height: 100% !important;
        }}
        .legend {{
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-top: 20px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 20px;
            height: 4px;
            border-radius: 2px;
        }}
        .legend-color.buy {{ background: #4CAF50; }}
        .legend-color.rent {{ background: #2196F3; }}
        .footer {{
            text-align: center;
            color: rgba(255,255,255,0.8);
            margin-top: 40px;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>香港房产价格趋势图</h1>
        <p class="subtitle">数据来源：28hse 成交记录 | 时间范围：2025年1月 - 2026年2月 | 统计周期：周（周一为起始日）</p>
        
        <div class="stats-grid">
            <div class="stat-card buy">
                <div class="stat-title buy">买卖平均尺价统计</div>
                <div class="stat-row">
                    <span class="stat-label">数据点数</span>
                    <span class="stat-value">{len(buy_prices)} 周</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最小值</span>
                    <span class="stat-value">${buy_min:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最大值</span>
                    <span class="stat-value">${buy_max:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">平均值</span>
                    <span class="stat-value">${buy_avg:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最新值</span>
                    <span class="stat-value">${buy_latest:,.2f}/ft²</span>
                </div>
            </div>
            
            <div class="stat-card rent">
                <div class="stat-title rent">租赁平均尺价统计</div>
                <div class="stat-row">
                    <span class="stat-label">数据点数</span>
                    <span class="stat-value">{len(rent_prices)} 周</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最小值</span>
                    <span class="stat-value">${rent_min:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最大值</span>
                    <span class="stat-value">${rent_max:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">平均值</span>
                    <span class="stat-value">${rent_avg:,.2f}/ft²</span>
                </div>
                <div class="stat-row">
                    <span class="stat-label">最新值</span>
                    <span class="stat-value">${rent_latest:,.2f}/ft²</span>
                </div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">买卖平均尺价趋势</div>
            <div class="chart-wrapper">
                <canvas id="buyChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">租赁平均尺价趋势</div>
            <div class="chart-wrapper">
                <canvas id="rentChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">买卖与租赁价格对比</div>
            <div class="chart-wrapper">
                <canvas id="compareChart"></canvas>
            </div>
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-color buy"></div>
                    <span>买卖平均尺价</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color rent"></div>
                    <span>租赁平均尺价</span>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>

    <script>
        // 数据
        const buyDates = {buy_dates};
        const buyPrices = {buy_prices};
        const rentDates = {rent_dates};
        const rentPrices = {rent_prices};

        // 绘制折线图的函数
        function drawLineChart(canvasId, dates, prices, color, fillColor, yAxisLabel) {{
            const canvas = document.getElementById(canvasId);
            const ctx = canvas.getContext('2d');
            
            // 设置canvas尺寸
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width * 2;
            canvas.height = rect.height * 2;
            ctx.scale(2, 2);
            
            const width = rect.width;
            const height = rect.height;
            const padding = {{ top: 40, right: 40, bottom: 80, left: 80 }};
            const chartWidth = width - padding.left - padding.right;
            const chartHeight = height - padding.top - padding.bottom;
            
            // 清空画布
            ctx.clearRect(0, 0, width, height);
            
            // 计算比例
            const minPrice = Math.min(...prices) * 0.98;
            const maxPrice = Math.max(...prices) * 1.02;
            const priceRange = maxPrice - minPrice;
            
            // 绘制网格线
            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 1;
            
            // 水平网格线
            for (let i = 0; i <= 5; i++) {{
                const y = padding.top + (chartHeight / 5) * i;
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(padding.left + chartWidth, y);
                ctx.stroke();
                
                // Y轴标签
                ctx.fillStyle = '#666';
                ctx.font = '12px Arial';
                ctx.textAlign = 'right';
                const price = maxPrice - (priceRange / 5) * i;
                ctx.fillText('$' + price.toFixed(0), padding.left - 10, y + 4);
            }}
            
            // 绘制数据线
            ctx.strokeStyle = color;
            ctx.lineWidth = 3;
            ctx.beginPath();
            
            const points = prices.map((price, index) => ({{
                x: padding.left + (index / (prices.length - 1)) * chartWidth,
                y: padding.top + chartHeight - ((price - minPrice) / priceRange) * chartHeight
            }}));
            
            // 使用贝塞尔曲线使线条更平滑
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {{
                const prev = points[i - 1];
                const curr = points[i];
                const cpx = (prev.x + curr.x) / 2;
                ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
            }}
            ctx.stroke();
            
            // 填充区域
            ctx.fillStyle = fillColor;
            ctx.beginPath();
            ctx.moveTo(points[0].x, padding.top + chartHeight);
            ctx.lineTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {{
                const prev = points[i - 1];
                const curr = points[i];
                const cpx = (prev.x + curr.x) / 2;
                ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
            }}
            ctx.lineTo(points[points.length - 1].x, padding.top + chartHeight);
            ctx.closePath();
            ctx.fill();
            
            // 绘制数据点
            points.forEach((point, index) => {{
                if (index % Math.ceil(points.length / 10) === 0 || index === points.length - 1) {{
                    ctx.fillStyle = color;
                    ctx.beginPath();
                    ctx.arc(point.x, point.y, 5, 0, Math.PI * 2);
                    ctx.fill();
                    
                    // 白色边框
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}
            }});
            
            // X轴标签（每5个显示一个）
            ctx.fillStyle = '#666';
            ctx.font = '11px Arial';
            ctx.textAlign = 'center';
            const step = Math.ceil(dates.length / 8);
            for (let i = 0; i < dates.length; i += step) {{
                const x = padding.left + (i / (dates.length - 1)) * chartWidth;
                const date = dates[i].substring(5); // 只显示月-日
                ctx.save();
                ctx.translate(x, padding.top + chartHeight + 20);
                ctx.rotate(-Math.PI / 4);
                ctx.fillText(date, 0, 0);
                ctx.restore();
            }}
            
            // Y轴标题
            ctx.save();
            ctx.translate(20, height / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.textAlign = 'center';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#333';
            ctx.fillText(yAxisLabel, 0, 0);
            ctx.restore();
        }}

        // 绘制对比图（双Y轴）
        function drawCompareChart(canvasId, dates, buyPrices, rentPrices) {{
            const canvas = document.getElementById(canvasId);
            const ctx = canvas.getContext('2d');
            
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width * 2;
            canvas.height = rect.height * 2;
            ctx.scale(2, 2);
            
            const width = rect.width;
            const height = rect.height;
            const padding = {{ top: 40, right: 80, bottom: 80, left: 80 }};
            const chartWidth = width - padding.left - padding.right;
            const chartHeight = height - padding.top - padding.bottom;
            
            ctx.clearRect(0, 0, width, height);
            
            // 计算比例
            const buyMin = Math.min(...buyPrices) * 0.98;
            const buyMax = Math.max(...buyPrices) * 1.02;
            const buyRange = buyMax - buyMin;
            
            const rentMin = Math.min(...rentPrices) * 0.98;
            const rentMax = Math.max(...rentPrices) * 1.02;
            const rentRange = rentMax - rentMin;
            
            // 绘制网格线
            ctx.strokeStyle = '#e0e0e0';
            ctx.lineWidth = 1;
            
            for (let i = 0; i <= 5; i++) {{
                const y = padding.top + (chartHeight / 5) * i;
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(padding.left + chartWidth, y);
                ctx.stroke();
            }}
            
            // 绘制买卖数据线（左Y轴）
            ctx.strokeStyle = '#4CAF50';
            ctx.lineWidth = 3;
            ctx.beginPath();
            
            const buyPoints = buyPrices.map((price, index) => ({{
                x: padding.left + (index / (buyPrices.length - 1)) * chartWidth,
                y: padding.top + chartHeight - ((price - buyMin) / buyRange) * chartHeight
            }}));
            
            ctx.moveTo(buyPoints[0].x, buyPoints[0].y);
            for (let i = 1; i < buyPoints.length; i++) {{
                const prev = buyPoints[i - 1];
                const curr = buyPoints[i];
                const cpx = (prev.x + curr.x) / 2;
                ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
            }}
            ctx.stroke();
            
            // 绘制租赁数据线（右Y轴）
            ctx.strokeStyle = '#2196F3';
            ctx.lineWidth = 3;
            ctx.beginPath();
            
            const rentPoints = rentPrices.map((price, index) => ({{
                x: padding.left + (index / (rentPrices.length - 1)) * chartWidth,
                y: padding.top + chartHeight - ((price - rentMin) / rentRange) * chartHeight
            }}));
            
            ctx.moveTo(rentPoints[0].x, rentPoints[0].y);
            for (let i = 1; i < rentPoints.length; i++) {{
                const prev = rentPoints[i - 1];
                const curr = rentPoints[i];
                const cpx = (prev.x + curr.x) / 2;
                ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
            }}
            ctx.stroke();
            
            // 绘制数据点
            buyPoints.forEach((point, index) => {{
                if (index % Math.ceil(buyPoints.length / 8) === 0 || index === buyPoints.length - 1) {{
                    ctx.fillStyle = '#4CAF50';
                    ctx.beginPath();
                    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}
            }});
            
            rentPoints.forEach((point, index) => {{
                if (index % Math.ceil(rentPoints.length / 8) === 0 || index === rentPoints.length - 1) {{
                    ctx.fillStyle = '#2196F3';
                    ctx.beginPath();
                    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
                    ctx.fill();
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }}
            }});
            
            // 左Y轴标签（买卖）
            ctx.fillStyle = '#4CAF50';
            ctx.font = '12px Arial';
            ctx.textAlign = 'right';
            for (let i = 0; i <= 5; i++) {{
                const y = padding.top + (chartHeight / 5) * i;
                const price = buyMax - (buyRange / 5) * i;
                ctx.fillText('$' + (price/1000).toFixed(1) + 'K', padding.left - 10, y + 4);
            }}
            
            // 右Y轴标签（租赁）
            ctx.fillStyle = '#2196F3';
            ctx.textAlign = 'left';
            for (let i = 0; i <= 5; i++) {{
                const y = padding.top + (chartHeight / 5) * i;
                const price = rentMax - (rentRange / 5) * i;
                ctx.fillText('$' + price.toFixed(0), padding.left + chartWidth + 10, y + 4);
            }}
            
            // X轴标签
            ctx.fillStyle = '#666';
            ctx.font = '11px Arial';
            ctx.textAlign = 'center';
            const step = Math.ceil(dates.length / 8);
            for (let i = 0; i < dates.length; i += step) {{
                const x = padding.left + (i / (dates.length - 1)) * chartWidth;
                const date = dates[i].substring(5);
                ctx.save();
                ctx.translate(x, padding.top + chartHeight + 20);
                ctx.rotate(-Math.PI / 4);
                ctx.fillText(date, 0, 0);
                ctx.restore();
            }}
            
            // Y轴标题
            ctx.save();
            ctx.translate(25, height / 2);
            ctx.rotate(-Math.PI / 2);
            ctx.textAlign = 'center';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#4CAF50';
            ctx.fillText('买卖尺价 ($/ft²)', 0, 0);
            ctx.restore();
            
            ctx.save();
            ctx.translate(width - 25, height / 2);
            ctx.rotate(Math.PI / 2);
            ctx.textAlign = 'center';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#2196F3';
            ctx.fillText('租赁尺价 ($/ft²)', 0, 0);
            ctx.restore();
        }}

        // 初始化图表
        window.addEventListener('load', () => {{
            drawLineChart('buyChart', buyDates, buyPrices, '#4CAF50', 'rgba(76, 175, 80, 0.1)', '平均尺价 ($/ft²)');
            drawLineChart('rentChart', rentDates, rentPrices, '#2196F3', 'rgba(33, 150, 243, 0.1)', '平均尺价 ($/ft²)');
            drawCompareChart('compareChart', buyDates, buyPrices, rentPrices);
        }});

        // 响应窗口大小变化
        window.addEventListener('resize', () => {{
            drawLineChart('buyChart', buyDates, buyPrices, '#4CAF50', 'rgba(76, 175, 80, 0.1)', '平均尺价 ($/ft²)');
            drawLineChart('rentChart', rentDates, rentPrices, '#2196F3', 'rgba(33, 150, 243, 0.1)', '平均尺价 ($/ft²)');
            drawCompareChart('compareChart', buyDates, buyPrices, rentPrices);
        }});
    </script>
</body>
</html>
'''
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"图表已生成: {output_file}")
    except Exception as e:
        logger.error(f"生成图表失败: {e}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("开始生成价格趋势图表")
    logger.info("=" * 60)
    
    # 加载数据
    data = load_trend_data(CONFIG["input_file"])
    
    if not data:
        logger.error("没有数据可生成图表")
        return
    
    # 生成HTML图表
    output_file = f"{CONFIG['output_prefix']}_charts.html"
    generate_html_chart(data, output_file)
    
    logger.info("\n处理完成!")
    logger.info(f"请在浏览器中打开: {output_file}")


if __name__ == "__main__":
    main()
