# 28hse 私人屋苑爬虫使用指南

## 安装依赖

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 运行爬虫脚本

```bash
python scrape_estates.py
```

### 2. 输出文件

运行完成后会生成两个JSON文件：

- `estates_mapping.json` - 简单的楼宇名称→ID映射
- `estates_mapping_detailed.json` - 包含区域和URL的详细信息

## 输出格式

### estates_mapping.json
```json
{
  "偉景花園": "4676",
  "映灣園": "4710",
  "天晉": "6558",
  "嘉湖山莊": "4390"
}
```

### estates_mapping_detailed.json
```json
{
  "4676": {
    "name": "偉景花園",
    "id": "4676",
    "area": "新界",
    "url": "https://www.28hse.com/buy/apartment/a3/dg51/di51-123/c4676"
  }
}
```

## 在代码中使用

```python
from scrape_estates import EstateIDScraper

# 创建爬虫实例
scraper = EstateIDScraper()

# 爬取所有区域
scraper.scrape_all_areas()

# 获取映射字典
mapping = scraper.get_mapping()

# 查找特定屋苑的ID
estate_id = mapping.get("偉景花園")
print(f"偉景花園的ID是: {estate_id}")

# 保存结果
scraper.save_results('my_estates.json')
```

## 特点

✅ **高效**: 只需4次HTTP请求覆盖全港所有区域  
✅ **完整**: 获取所有有活跃房产的私人屋苑  
✅ **去重**: 自动去除重复的屋苑  
✅ **详细**: 包含屋苑名称、ID、区域、URL等信息

## 技术说明

- 使用区域搜索API: `/property/dosearch`
- 4个区域: 香港島、九龍、新界、離島
- 从HTML响应中提取屋苑链接和ID
- 正则表达式匹配URL中的楼宇ID (c{数字})

## 注意事项

- 请求间隔1秒，避免给服务器造成压力
- 使用浏览器User-Agent模拟真实访问
- 仅爬取公开可访问的数据
