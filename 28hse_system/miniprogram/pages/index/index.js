// pages/index/index.js - 首页地图逻辑
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')
const { getCache, setCache } = require('../../utils/cache.js')

Page({
  data: {
    // 地图配置
    centerLat: 22.3193,  // 香港中心纬度
    centerLng: 114.1694, // 香港中心经度
    scale: 11,           // 缩放级别
    
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
    loading: true
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
      // 先尝试从缓存读取
      const cachedEstates = getCache('all_estates')
      if (cachedEstates) {
        this.setData({
          allEstates: cachedEstates.data,
          loading: false
        })
        this.loadMarkersInView()
        wx.hideLoading()
        return
      }

      // 从API加载
      const res = await api.getAllEstates()
      if (res.success) {
        setCache('all_estates', res)
        this.setData({
          allEstates: res.data,
          loading: false
        })
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
  loadMarkersInView() {
    const { allEstates, centerLat, centerLng, scale, minRatio, maxRatio } = this.data
    
    if (!allEstates || allEstates.length === 0) return
    
    // 根据scale计算可视范围(简化算法)
    const range = 0.5 / scale
    
    // 筛选可视区域内的小区
    const visibleEstates = allEstates.filter(estate => {
      if (!estate.coordinates) return false
      const lat = estate.coordinates.latitude
      const lng = estate.coordinates.longitude
      return Math.abs(lat - centerLat) < range && 
             Math.abs(lng - centerLng) < range
    })
    
    // 限制最多500个标记
    const limitedEstates = visibleEstates.slice(0, 500)
    
    // 转换为markers格式
    const markers = limitedEstates.map((estate, index) => {
      const color = getRentRatioColor(estate.rent_ratio, minRatio, maxRatio)
      return {
        id: index,
        latitude: estate.coordinates.latitude,
        longitude: estate.coordinates.longitude,
        width: 20,
        height: 20,
        callout: {
          content: estate.name,
          color: '#333',
          fontSize: 12,
          borderRadius: 5,
          bgColor: '#fff',
          padding: 5,
          display: 'BYCLICK'
        },
        customData: {
          estateId: estate.id,
          estateName: estate.name,
          rentRatio: estate.rent_ratio
        },
        // 使用label显示颜色圆点
        label: {
          content: '●',
          color: color,
          fontSize: 20,
          x: 0,
          y: 0
        }
      }
    })
    
    this.setData({ markers })
    console.log(`加载了 ${markers.length} 个标记`)
  },

  // 地图区域变化时重新加载标记
  onRegionChange(e) {
    if (e.type === 'end') {
      const mapCtx = wx.createMapContext('estate-map', this)
      mapCtx.getCenterLocation({
        success: (res) => {
          this.setData({
            centerLat: res.latitude,
            centerLng: res.longitude
          })
          // 延迟加载,避免频繁触发
          clearTimeout(this.regionChangeTimer)
          this.regionChangeTimer = setTimeout(() => {
            this.loadMarkersInView()
          }, 500)
        }
      })
      
      // 获取当前缩放级别
      mapCtx.getScale({
        success: (res) => {
          this.setData({ scale: res.scale })
        }
      })
    }
  },

  // 点击标记
  onMarkerTap(e) {
    const marker = this.data.markers[e.detail.markerId]
    if (marker && marker.customData) {
      // 跳转到详情页
      wx.navigateTo({
        url: `/pages/estate-detail/estate-detail?id=${marker.customData.estateId}`
      })
    }
  },

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
  
  preventClose(e) {
    // 阻止事件冒泡,防止点击图例内容时关闭
    e.stopPropagation()
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
