// pages/search/search.js - 搜索页逻辑
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')
const { debounce } = require('../../utils/util.js')

Page({
  data: {
    keyword: '',
    results: [],
    searched: false,
    searching: false,
    minRatio: 0,
    maxRatio: 10
  },

  onLoad(options) {
    // 加载租售比范围(用于颜色计算)
    this.loadRatioRange()
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

  // 输入框变化(使用防抖)
  onKeywordChange: debounce(function(e) {
    const keyword = e.detail.value
    this.setData({ keyword })
    
    // 自动搜索
    if (keyword && keyword.length >= 2) {
      this.onSearch()
    } else if (!keyword) {
      this.setData({ results: [], searched: false })
    }
  }, 500),

  // 执行搜索
  async onSearch() {
    const { keyword } = this.data
    
    if (!keyword || keyword.trim() === '') {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }

    this.setData({ searching: true })

    try {
      const res = await api.searchEstates(keyword.trim())
      
      if (res.success) {
        // 为每个结果添加颜色信息
        const results = res.data.map(estate => ({
          ...estate,
          ratioColor: getRentRatioColor(
            estate.rent_ratio,
            this.data.minRatio,
            this.data.maxRatio
          )
        }))
        
        this.setData({
          results: results,
          searched: true,
          searching: false
        })
      }
    } catch (error) {
      console.error('搜索失败:', error)
      wx.showToast({ title: '搜索失败', icon: 'none' })
      this.setData({ searching: false, searched: true })
    }
  },

  // 选择小区
  selectEstate(e) {
    const estateId = e.currentTarget.dataset.estateId
    if (estateId) {
      wx.navigateTo({
        url: `/pages/estate-detail/estate-detail?id=${estateId}`
      })
    }
  },

  // 清除关键词
  clearKeyword() {
    this.setData({
      keyword: '',
      results: [],
      searched: false
    })
  }
})
