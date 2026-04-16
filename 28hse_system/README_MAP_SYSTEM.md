# 香港小区租售比地图可视化系统

一个基于Vue.js + Flask + Leaflet.js的香港小区租售比地图可视化系统,整合小区静态信息和租售比数据,提供交互式地图展示和搜索功能。

## 系统架构

### 技术栈
- **前端**: Vue.js 3 + Leaflet.js + Axios
- **后端**: Python Flask + Flask-CORS
- **地图**: Leaflet.js + OpenStreetMap
- **构建工具**: Vite

### 项目结构
```
28hse/
├── backend/                    # Flask后端服务
│   ├── app.py                 # Flask主应用
│   ├── requirements.txt       # Python依赖
│   └── utils/
│       └── data_loader.py     # 数据加载和整合工具
├── frontend/                   # Vue.js前端应用
│   ├── index.html             # 入口HTML
│   ├── package.json           # Node依赖
│   ├── vite.config.js         # Vite配置
│   └── src/
│       ├── main.js            # Vue入口
│       ├── App.vue            # 根组件
│       ├── components/        # Vue组件
│       │   ├── MapView.vue    # 地图主组件
│       │   ├── SearchBar.vue  # 搜索组件
│       │   └── ColorLegend.vue # 色彩图例组件
│       └── utils/             # 工具函数
│           ├── api.js         # API封装
│           └── colorUtils.js  # 颜色映射工具
├── estate_static_info.json    # 小区静态信息
├── average_rent_sale_ratio.json # 租售比数据
├── start.sh                   # 启动脚本
└── README_MAP_SYSTEM.md       # 本文档
```

## 核心功能

### 1. 地图可视化
- 基于Leaflet.js的交互式地图
- 显示所有有坐标的香港小区
- 圆形标记,颜色根据租售比渐变(绿色→红色)
- 租售比越低显示越绿,越高显示越红
- 无租售比数据的小区显示为灰色

### 2. 信息弹窗
点击地图标记显示小区详细信息:
- 小区名称
- 小区ID
- 地址
- 建立时间
- 开发商
- 座数
- 租售比值

### 3. 搜索功能
- 实时搜索小区名称(支持中文模糊匹配)
- 显示搜索结果列表(最多10条)
- 点击搜索结果自动定位并打开详情

### 4. 色彩图例
- 显示租售比与颜色的对应关系
- 渐变色条(绿→黄→橙→红)
- 标注最小值、中位数、最大值

### 5. 数据统计
- 小区总数
- 平均租售比

## API文档

### 基础信息
- **Base URL**: `http://localhost:5000/api`
- **响应格式**: JSON

### API端点

#### 1. 获取所有小区列表
```
GET /api/estates
```

**响应示例**:
```json
{
  "success": true,
  "count": 1325,
  "data": [
    {
      "id": "3060",
      "name": "黃埔花園",
      "address": "必嘉街121號",
      "coordinates": {
        "latitude": 22.27642,
        "longitude": 114.17063
      },
      "rent_ratio": 2.5
    }
  ]
}
```

#### 2. 获取特定小区详情
```
GET /api/estates/<estate_id>
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "id": "3060",
    "name": "黃埔花園",
    "address": "必嘉街121號",
    "coordinates": {...},
    "rent_ratio": 2.5,
    "establish_year": "1985 年",
    "developer": "和記黃埔",
    "building_count": "88座",
    "units": "10433伙",
    "management_company": "和記黃埔管理有限公司",
    "facilities": "...",
    "parking_spaces": "2900個"
  }
}
```

#### 3. 获取租售比统计信息
```
GET /api/rent-ratios
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "min": 1.7699,
    "max": 6.1969,
    "average": 3.5423,
    "count": 1325,
    "data": {
      "200": 1.9538,
      "201": 2.0871,
      ...
    }
  }
}
```

#### 4. 搜索小区
```
GET /api/search?keyword=<关键词>
```

**参数**:
- `keyword`: 搜索关键词(必需)

**响应示例**:
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": "3060",
      "name": "黃埔花園",
      "address": "必嘉街121號",
      "coordinates": {...},
      "rent_ratio": 2.5
    }
  ]
}
```

## 安装步骤

### 前置要求
- Python 3.7+
- Node.js 16+
- npm 或 yarn

### 方式一: 使用启动脚本(推荐)

```bash
# 1. 进入项目目录
cd /home/zhangchi/Documents/28hse

# 2. 运行启动脚本
./start.sh
```

启动脚本会自动:
- 创建Python虚拟环境
- 安装后端依赖
- 启动Flask服务器

### 方式二: 手动启动

#### 后端启动

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境(首次运行)
python3 -m venv venv

# 3. 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动Flask服务
python app.py
```

后端服务将在 `http://localhost:5000` 启动

#### 前端开发模式

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev
```

前端开发服务器将在 `http://localhost:3000` 启动

#### 前端生产构建

```bash
# 1. 进入前端目录
cd frontend

# 2. 构建生产版本
npm run build
```

构建文件将生成到 `frontend/dist/` 目录,Flask会自动服务这些文件。

## 运行方式

### 开发模式
1. 启动后端: `cd backend && python app.py`
2. 启动前端: `cd frontend && npm run dev`
3. 访问前端开发服务器: http://localhost:3000

**优点**: 热重载,实时查看修改效果

### 生产模式
1. 构建前端: `cd frontend && npm run build`
2. 启动后端: `cd backend && python app.py`
3. 访问Flask服务器: http://localhost:5000

**优点**: 单一服务器,部署简单

## 数据源说明

### 1. estate_static_info.json
包含小区的静态信息,结构如下:
```json
{
  "小区ID": {
    "name": "小区名称",
    "id": "小区ID",
    "address": "地址",
    "coordinates": {
      "latitude": 纬度,
      "longitude": 经度
    },
    "basic_info": {
      "establish_year": "建立年份",
      "developer": "开发商",
      "building_count": "座数",
      ...
    }
  }
}
```

### 2. average_rent_sale_ratio.json
包含租售比数据,结构如下:
```json
{
  "metadata": {
    "description": "平均租售比计算结果",
    "unit": "百分比 (%)",
    "formula": "(月租金单价 * 12) / 售价单价 * 100",
    "total_estates": 1325
  },
  "data": {
    "小区ID": 租售比数值,
    ...
  }
}
```

## 色彩映射算法

使用HSL色彩空间实现平滑渐变:
- **低租售比(接近最小值)**: HSL(120°, 80%, 50%) - 绿色
- **高租售比(接近最大值)**: HSL(0°, 80%, 50%) - 红色
- **无数据**: #999999 - 灰色

色相从120°(绿)线性变化到0°(红),确保视觉区分度。

## 性能优化

1. **数据缓存**: 使用`functools.lru_cache`缓存文件读取
2. **API响应**: 仅返回必要字段,减少数据传输
3. **前端渲染**: Leaflet.js直接渲染1325个标记,无需额外优化
4. **搜索防抖**: 300ms延迟,减少API调用

## 容错处理

### 后端
- 文件读取异常捕获
- API错误统一返回友好信息
- 404/500错误处理器

### 前端
- API请求失败显示错误提示
- 加载状态指示器
- 数据缺失优雅降级(无坐标不显示,无租售比显示灰色)

## 响应式设计

- **桌面端**: 侧边栏(350px) + 地图(剩余空间)
- **移动端**: 侧边栏(40vh) + 地图(60vh),垂直布局

## 常见问题

### Q: 为什么某些小区没有显示在地图上?
A: 只有同时满足以下条件的小区才会显示:
1. 在`estate_static_info.json`中存在
2. 有有效的坐标信息(latitude和longitude)

### Q: 为什么某些小区显示为灰色?
A: 该小区在`average_rent_sale_ratio.json`中没有租售比数据。

### Q: 如何更新数据?
A: 替换`estate_static_info.json`和`average_rent_sale_ratio.json`文件后,重启Flask服务器即可。数据会被重新加载。

### Q: 端口被占用怎么办?
A: 修改以下配置:
- Flask端口: `backend/app.py` 第165行 `port=5000`
- Vite端口: `frontend/vite.config.js` 第7行 `port: 3000`

## 后续扩展建议

1. **标记聚合**: 如果小区数量超过2000个,考虑使用Leaflet.markercluster插件
2. **筛选功能**: 添加按区域、租售比范围筛选
3. **数据导出**: 提供CSV/Excel导出功能
4. **趋势分析**: 显示租售比随时间变化的趋势
5. **用户认证**: 添加登录功能,保存用户收藏的小区

## 技术支持

如有问题,请检查:
1. 数据文件是否存在且格式正确
2. Python依赖是否完整安装
3. Node.js依赖是否完整安装
4. 端口是否被占用

## 许可证

MIT License

---

**开发日期**: 2026年2月  
**版本**: 1.0.0
