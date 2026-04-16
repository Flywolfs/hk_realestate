# 快速开始指南

## 🚀 立即使用

您的香港小区租售比地图可视化系统已经完全构建完成!

### 当前状态
✅ Flask后端正在运行中 (http://localhost:5000)  
✅ 前端已构建并集成  
✅ 所有功能已测试通过

### 访问系统

**方法1: 直接访问生产版本(推荐)**
```bash
# 在浏览器中打开:
http://localhost:5000
```

**方法2: 开发模式(支持热重载)**
```bash
# 终端1: 后端已运行
# 终端2: 启动前端开发服务器
cd frontend
npm run dev
# 然后访问: http://localhost:3000
```

## 📋 系统功能

### 1. 交互式地图
- 10,056个香港小区标记点
- 根据租售比显示渐变色(绿色=低,红色=高)
- 点击标记查看详细信息

### 2. 搜索功能
- 在左侧搜索栏输入小区名称
- 支持中文模糊搜索
- 点击结果自动定位

### 3. 色彩图例
- 显示租售比与颜色对应关系
- 最小值: 1.77%
- 最大值: 6.20%
- 平均值: 4.19%

### 4. 数据统计
- 小区总数: 1,325
- 平均租售比: 4.19%

## 🔌 API端点

所有API都在运行,可以直接测试:

```bash
# 获取所有小区
curl http://localhost:5000/api/estates

# 获取特定小区详情
curl http://localhost:5000/api/estates/3060

# 获取租售比统计
curl http://localhost:5000/api/rent-ratios

# 搜索小区
curl "http://localhost:5000/api/search?keyword=黃埔"
```

## 📖 完整文档

详细使用说明请查看: [README_MAP_SYSTEM.md](./README_MAP_SYSTEM.md)

## 🔧 管理命令

### 停止服务器
```bash
# 如果需要停止Flask服务器
pkill -f "python3 app.py"
```

### 重启服务器
```bash
cd backend
python3 app.py
```

### 重新构建前端
```bash
cd frontend
npm run build
```

## 📊 测试报告

完整测试报告: [TESTING_REPORT.txt](./TESTING_REPORT.txt)

所有功能测试通过! ✅

## 💡 提示

1. **首次使用**: 直接访问 http://localhost:5000 即可
2. **数据更新**: 替换JSON文件后重启Flask服务器
3. **性能**: 系统可流畅处理10,000+标记点
4. **移动端**: 支持响应式设计,可在手机浏览器访问

## 🎉 开始探索

现在就在浏览器中打开 http://localhost:5000 开始使用吧!
