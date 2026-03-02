// pages/index/index.js - 首页地图逻辑
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')
const { getCache, setCache } = require('../../utils/cache.js')
const { batchTransformEstates } = require('../../utils/coordTransform.js')

Page({
  data: {
    // 地图配置
    centerLat: 22.3193,  // 香港中心纬度
    centerLng: 114.1694, // 香港中心经度
    scale: 11,           // 缩放级别
    
    // 地图样式 - 使用清爽风格
    mapStyle: 'style1',  // style1: 标准样式, style2: 卫星图
    
    // 标记数据
    markers: [],
    allEstates: [],      // 所有小区数据
    
    // 统计数据
    estateCount: 0,
    avgRatio: 0,
    minRatio: 0,
    maxRatio: 10,
    
    // UI状态
    showStats: true,
    showLegend: false,
    loading: true,
    
    // 点击的marker信息（用于显示浮窗）
    selectedEstate: null,
    showEstateCard: false
  },

  onLoad() {
    console.log('首页加载')
    // 页面加载时初始化
    this.loadRentRatioStats()
    this.loadEstates()
  },

  onShow() {
    // 检查是否有从详情页返回的定位信息
    const app = getApp()
    if (app.globalData.locateEstate) {
      const estate = app.globalData.locateEstate
      this.setData({
        centerLat: estate.lat,
        centerLng: estate.lng,
        scale: 15
      })
      this.loadMarkersInView()
      app.globalData.locateEstate = null
    }
  },

  // 加载租售比统计
  async loadRentRatioStats() {
    try {
      // 先尝试从缓存读取
      const cachedStats = getCache('rent_ratio_stats')
      if (cachedStats) {
        this.setData({
          minRatio: cachedStats.data.min,
          maxRatio: cachedStats.data.max,
          avgRatio: cachedStats.data.average.toFixed(2),
          estateCount: cachedStats.data.count
        })
        return
      }

      // 从API加载
      const res = await api.getRentRatioStats()
      if (res.success) {
        setCache('rent_ratio_stats', res)
        this.setData({
          minRatio: res.data.min,
          maxRatio: res.data.max,
          avgRatio: res.data.average.toFixed(2),
          estateCount: res.data.count
        })
      }
    } catch (error) {
      console.error('加载统计失败:', error)
      wx.showToast({ title: '加载统计失败', icon: 'none' })
    }
  },

  // 加载小区数据
  async loadEstates() {
    wx.showLoading({ title: '加载中...' })
    try {
      // 先尝试从缓存读取（缓存的已是过滤+转换后的数据）
      const cachedEstates = getCache('all_estates_processed')
      if (cachedEstates) {
        console.log(`命中缓存，共 ${cachedEstates.length} 条屋苑`)
        this.setData({ allEstates: cachedEstates, loading: false })
        this.loadMarkersInView()
        wx.hideLoading()
        return
      }

      // 从API加载原始数据
      const res = await api.getAllEstates()
      if (res.success) {
        const rawData = res.data

        // 1. 过滤没有租售比数据的屋苑（灰色点）
        const filteredEstates = rawData.filter(
          estate => estate.rent_ratio !== null && estate.rent_ratio !== undefined
        )
        console.log(`总屋苑: ${rawData.length}, 有租售比数据: ${filteredEstates.length}`)

        // 2. WGS-84 → GCJ-02 坐标转换
        const processedEstates = batchTransformEstates(filteredEstates)
        console.log('坐标转换完成，示例:', processedEstates[0]?.name, processedEstates[0]?.coordinates)

        // 缓存处理后的数据，避免重复遍历
        setCache('all_estates_processed', processedEstates)

        this.setData({ allEstates: processedEstates, loading: false })
        this.loadMarkersInView()
      }
    } catch (error) {
      console.error('加载小区失败:', error)
      wx.showToast({ title: '加载失败', icon: 'none' })
      this.setData({ loading: false })
    } finally {
      wx.hideLoading()
    }
  },

  // 加载可视区域内的标记(性能优化)
  async loadMarkersInView() {
    const { allEstates, centerLat, centerLng, scale, minRatio, maxRatio } = this.data
    
    if (!allEstates || allEstates.length === 0) return
    
    // 根据scale计算可视范围
    const latRange = 1 / Math.pow(2, scale - 8)
    const lngRange = 1.5 / Math.pow(2, scale - 8)
    
    // 筛选可视区域内的小区
    const visibleEstates = allEstates.filter(estate => {
      if (!estate.coordinates) return false
      const lat = estate.coordinates.latitude
      const lng = estate.coordinates.longitude
      if (!lat || !lng || lat === 0 || lng === 0) return false
      return Math.abs(lat - centerLat) <= latRange && 
             Math.abs(lng - centerLng) <= lngRange
    })
    
    // 根据缩放级别动态调整显示数量
    const maxMarkers = scale < 11 ? 200 : (scale < 13 ? 300 : 500)
    const limitedEstates = visibleEstates.slice(0, maxMarkers)
    
    console.log(`可视: ${visibleEstates.length}, 渲染: ${limitedEstates.length}`)
    
    // 收集当前需要的所有颜色，预生成尚未缓存的图标
    const colors = [...new Set(limitedEstates.map(e => getRentRatioColor(e.rent_ratio, minRatio, maxRatio)))]
    await Promise.all(colors.map(c => this._getOrCreateIcon(c)))
    
    // 构建 markers
    const markers = limitedEstates.map((estate, index) => {
      const color = getRentRatioColor(estate.rent_ratio, minRatio, maxRatio)
      const iconPath = this._iconCache[color] || ''
      return {
        id: index,
        latitude: estate.coordinates.latitude,
        longitude: estate.coordinates.longitude,
        iconPath,        // 彩色圆形图标，本身即可点击
        width: 22,
        height: 22,
        anchor: { x: 0.5, y: 0.5 },
        customData: {
          estateId: estate.id,
          estateName: estate.name,
          rentRatio: estate.rent_ratio,
          address: estate.address
        },
        callout: { display: 'NONE' }
      }
    })
    
    console.log(`加载了 ${markers.length} 个标记`)
    this.setData({ markers })
  },

  // 获取并缓存彩色圆形图标（基于 Canvas动态生成）
  _getOrCreateIcon(color) {
    if (!this._iconCache) this._iconCache = {}
    if (this._iconCache[color]) return Promise.resolve(this._iconCache[color])
    
    return new Promise((resolve) => {
      try {
        const size = 44  // 实际像素大小（设大一些以应对高分屏）
        const canvas = wx.createOffscreenCanvas({ type: '2d', width: size, height: size })
        const ctx = canvas.getContext('2d')
        
        ctx.clearRect(0, 0, size, size)
        
        // 外圈白色轮廓，增强对地图的可读性
        ctx.beginPath()
        ctx.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * Math.PI)
        ctx.fillStyle = 'rgba(255, 255, 255, 0.85)'
        ctx.fill()
        
        // 内层彩色圆
        ctx.beginPath()
        ctx.arc(size / 2, size / 2, size / 2 - 4, 0, 2 * Math.PI)
        ctx.fillStyle = color
        ctx.fill()
        
        wx.canvasToTempFilePath({
          canvas,
          success: (res) => {
            this._iconCache[color] = res.tempFilePath
            resolve(res.tempFilePath)
          },
          fail: (err) => {
            console.error('图标生成失败:', err)
            resolve('')
          }
        })
      } catch (e) {
        console.error('创建 Canvas 失败:', e)
        resolve('')
      }
    })
  },

  // 地图区域变化时重新加载标记
  onRegionChange(e) {
    // 只在用户操作结束时触发更新
    if (e.type === 'end' && e.causedBy === 'drag') {
      const mapCtx = wx.createMapContext('estate-map', this)
      
      // 清除之前的定时器,实现防抖
      clearTimeout(this.regionChangeTimer)
      
      // 延迟800ms执行,避免频繁触发
      this.regionChangeTimer = setTimeout(() => {
        // 同时获取中心位置和缩放级别
        mapCtx.getCenterLocation({
          success: (res) => {
            mapCtx.getScale({
              success: (scaleRes) => {
                // 计算位置和缩放变化量
                const latDiff = Math.abs(res.latitude - this.data.centerLat)
                const lngDiff = Math.abs(res.longitude - this.data.centerLng)
                const scaleDiff = Math.abs(scaleRes.scale - this.data.scale)
                
                // 只有当位置或缩放变化超过阈值时才重新加载
                // 避免微小移动导致的重复渲染
                const threshold = 0.01  // 约1公里
                if (latDiff > threshold || lngDiff > threshold || scaleDiff > 0.5) {
                  console.log(`地图位置变化: Lat ${latDiff.toFixed(4)}, Lng ${lngDiff.toFixed(4)}, Scale ${scaleDiff.toFixed(1)}`)
                  this.setData({
                    centerLat: res.latitude,
                    centerLng: res.longitude,
                    scale: scaleRes.scale
                  })
                  this.loadMarkersInView()
                }
              }
            })
          }
        })
      }, 800)
    }
  },

  // 点击marker - 显示浮窗信息卡片
  onMarkerTap(e) {
    const marker = this.data.markers[e.detail.markerId]
    if (marker && marker.customData) {
      // 显示浮窗信息卡片
      this.setData({
        selectedEstate: marker.customData,
        showEstateCard: true
      })
    }
  },
  
  // 关闭信息卡片
  closeEstateCard() {
    this.setData({
      showEstateCard: false,
      selectedEstate: null
    })
  },
  
  // 查看详情
  viewEstateDetail() {
    const { selectedEstate } = this.data
    if (selectedEstate) {
      wx.navigateTo({
        url: `/pages/estate-detail/estate-detail?id=${selectedEstate.estateId}`
      })
    }
  },
  
  // 阻止事件冒泡（catchtap 已在 WXML 层面阻止，JS 无需操作）
  preventClose() {},

  // 显示搜索页
  showSearch() {
    wx.navigateTo({
      url: '/pages/search/search'
    })
  },

  // 显示/隐藏图例
  toggleLegend() {
    this.setData({ showLegend: !this.data.showLegend })
  },
  
  hideLegend() {
    this.setData({ showLegend: false })
  },

  // 重新定位
  relocate() {
    this.setData({
      centerLat: 22.3193,
      centerLng: 114.1694,
      scale: 11
    })
    this.loadMarkersInView()
    wx.showToast({ title: '已重置', icon: 'success', duration: 1000 })
  },

  // 分享配置
  onShareAppMessage() {
    return {
      title: '香港小区租售比地图',
      path: '/pages/index/index',
      imageUrl: ''  // 可以设置分享图片
    }
  }
})
