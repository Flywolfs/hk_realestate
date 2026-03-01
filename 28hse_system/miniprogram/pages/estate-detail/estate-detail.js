// pages/estate-detail/estate-detail.js - 小区详情页
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')

Page({
  data: {
    estate: null,
    loading: true,
    ratioColor: '#999',
    minRatio: 0,
    maxRatio: 10
  },

  onLoad(options) {
    const estateId = options.id
    if (estateId) {
      this.loadEstateDetail(estateId)
      this.loadRatioRange()
    }
  },

  async loadRatioRange() {
    try {
      const res = await api.getRentRatioStats()
      if (res.success) {
        this.setData({
          minRatio: res.data.min,
          maxRatio: res.data.max
        })
      }
    } catch (error) {
      console.error('加载租售比范围失败:', error)
    }
  },

  async loadEstateDetail(estateId) {
    wx.showLoading({ title: '加载中...' })
    try {
      const res = await api.getEstateDetail(estateId)
      if (res.success) {
        const color = getRentRatioColor(
          res.data.rent_ratio,
          this.data.minRatio,
          this.data.maxRatio
        )
        this.setData({
          estate: res.data,
          loading: false,
          ratioColor: color
        })
      }
    } catch (error) {
      console.error('加载小区详情失败:', error)
      wx.showToast({ title: '加载失败', icon: 'none' })
      this.setData({ loading: false })
    } finally {
      wx.hideLoading()
    }
  },

  // 在地图中显示
  showOnMap() {
    const { estate } = this.data
    if (estate && estate.coordinates) {
      const app = getApp()
      app.globalData.locateEstate = {
        lat: estate.coordinates.latitude,
        lng: estate.coordinates.longitude,
        name: estate.name
      }
      wx.navigateBack()
    }
  },

  // 分享配置
  onShareAppMessage() {
    const { estate } = this.data
    return {
      title: `${estate.name} - 租售比${estate.rent_ratio}%`,
      path: `/pages/estate-detail/estate-detail?id=${estate.id}`
    }
  }
})
