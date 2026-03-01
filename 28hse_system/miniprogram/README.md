# 香港小区租售比微信小程序

## 项目简介

这是一个展示香港小区租售比数据的微信小程序,基于原有的Web系统迁移而来。通过地图可视化的方式,用户可以直观地查看香港各个小区的租售比信息,并进行搜索和详情查看。

## 技术栈

- **前端**: 微信小程序原生开发(WXML + WXSS + JavaScript)
- **地图**: 微信原生 `<map>` 组件
- **后端**: Flask API(保持不变)
- **数据源**: 28hse和centanet爬虫系统

## 项目结构

```
miniprogram/
├── pages/                      # 页面目录
│   ├── index/                  # 首页(地图主页)
│   │   ├── index.js
│   │   ├── index.json
│   │   ├── index.wxml
│   │   └── index.wxss
│   ├── search/                 # 搜索页
│   │   ├── search.js
│   │   ├── search.json
│   │   ├── search.wxml
│   │   └── search.wxss
│   └── estate-detail/          # 小区详情页
│       ├── estate-detail.js
│       ├── estate-detail.json
│       ├── estate-detail.wxml
│       └── estate-detail.wxss
├── components/                 # 自定义组件
│   ├── color-legend/           # 色彩图例组件
│   │   ├── color-legend.js
│   │   ├── color-legend.json
│   │   ├── color-legend.wxml
│   │   └── color-legend.wxss
│   └── stats-panel/            # 统计面板组件
│       ├── stats-panel.js
│       ├── stats-panel.json
│       ├── stats-panel.wxml
│       └── stats-panel.wxss
├── utils/                      # 工具函数
│   ├── api.js                  # API封装
│   ├── colorUtils.js           # 色彩映射工具
│   ├── cache.js                # 缓存管理
│   └── util.js                 # 通用工具函数
├── images/                     # 图片资源
├── app.js                      # 小程序入口
├── app.json                    # 小程序全局配置
├── app.wxss                    # 全局样式
├── project.config.json         # 项目配置
└── sitemap.json                # 索引配置
```

## 核心功能

### 1. 地图展示
- 基于微信原生地图组件
- 显示1000+个香港小区位置
- 使用颜色标记表示租售比(绿色→红色)
- 可视区域动态加载优化性能

### 2. 搜索功能
- 支持小区名称模糊搜索
- 自动防抖优化
- 搜索结果实时显示

### 3. 小区详情
- 点击地图标记查看详情
- 显示租售比、地址、建立年份等信息
- 支持分享功能

### 4. 数据缓存
- 使用微信Storage API缓存数据
- 1小时缓存有效期
- 减少网络请求,提升性能

## 开发指南

### 环境准备

1. 安装[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 确保Flask后端正在运行

```bash
cd backend
python3 app.py
```

### 导入项目

1. 打开微信开发者工具
2. 选择"导入项目"
3. 选择 `miniprogram` 目录
4. 填写AppID(测试可使用测试号)

### 配置说明

#### 1. API地址配置

在 `miniprogram/utils/api.js` 中修改 `BASE_URL`:

```javascript
const BASE_URL = 'http://localhost:5000/api'  // 开发环境
// 生产环境需改为HTTPS域名
// const BASE_URL = 'https://your-domain.com/api'
```

#### 2. 开发者工具设置

- 勾选"不校验合法域名"(开发阶段)
- 勾选"不校验TLS版本"(开发阶段)
- 上线前需在微信公众平台配置服务器域名

### 调试技巧

1. **查看控制台日志**: 开发者工具 → Console标签
2. **查看网络请求**: 开发者工具 → Network标签
3. **清除缓存**: 工具 → 清除缓存
4. **真机调试**: 点击"真机调试"按钮

## API接口

小程序使用与Web端相同的Flask API接口:

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/estates` | GET | 获取所有小区列表 |
| `/api/estates/<id>` | GET | 获取小区详情 |
| `/api/rent-ratios` | GET | 获取租售比统计 |
| `/api/search?keyword=xxx` | GET | 搜索小区 |

## 性能优化

### 1. 地图标记优化
- 只加载可视区域内的标记(最多500个)
- 地图移动时延迟500ms后加载
- 使用label显示彩色圆点,减少自定义图标

### 2. 数据缓存
- 小区列表和统计数据缓存1小时
- 使用微信Storage API本地存储
- 自动过期清理机制

### 3. 请求优化
- 防抖处理搜索输入
- Promise.all并发请求
- 请求失败重试机制

## 部署上线

### 1. 准备工作

- [ ] 申请小程序账号
- [ ] 获取AppID
- [ ] 配置服务器域名(必须HTTPS)
- [ ] 申请腾讯位置服务密钥(如需地理定位)

### 2. 服务器配置

确保后端API支持HTTPS访问,参考 [计划文档](file:///home/zhangchi/.config/Qoder/SharedClientCache/cache/plans/Web系统迁移到微信小程序_fc49b504.md) 的第三章节。

### 3. 域名配置

在[微信公众平台](https://mp.weixin.qq.com/)配置:
- 开发 → 开发管理 → 开发设置 → 服务器域名
- request合法域名: `https://your-domain.com`

### 4. 提交审核

1. 在开发者工具中点击"上传"
2. 填写版本号和描述
3. 在公众平台提交审核
4. 审核通过后发布

## 常见问题

### Q1: 小程序无法请求本地API

**解决方案**:
- 开发阶段勾选"不校验合法域名"
- 或使用ngrok等工具进行内网穿透
- 或使用电脑局域网IP

### Q2: 地图组件不显示

**原因**:
- 坐标数据格式错误
- 地图组件权限未授予

**解决方案**:
- 检查坐标是否为GCJ-02格式
- 在app.json中配置地理位置权限

### Q3: 标记过多导致卡顿

**解决方案**:
- 已实现可视区域加载
- 限制单次最多500个标记
- 考虑实现标记聚合

### Q4: 数据加载缓慢

**解决方案**:
- 使用缓存机制(已实现)
- 优化后端API响应速度
- 考虑使用CDN加速

## 开发团队

本项目基于原有Web系统迁移,由AI辅助完成小程序版本开发。

## 许可证

MIT License

## 更新日志

### v1.0.0 (2026-03-01)
- ✅ 完成从Web端到小程序的迁移
- ✅ 实现地图展示功能
- ✅ 实现搜索功能
- ✅ 实现详情页
- ✅ 添加数据缓存
- ✅ 优化性能

## 下一步计划

- [ ] 添加小区详情页完整实现
- [ ] 实现收藏功能
- [ ] 添加用户登录
- [ ] 实现租售比趋势图
- [ ] 添加筛选功能
- [ ] 支持离线地图

## 联系方式

如有问题或建议,请通过以下方式联系:

- 项目仓库: (待添加)
- 反馈邮箱: (待添加)

---

**注意**: 本项目仅用于学习和研究目的,数据来源于公开网站。
