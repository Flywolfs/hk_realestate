// pages/search/search.js - 搜索页逻辑
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')
const { debounce } = require('../../utils/util.js')
const { toSimplified, toTraditional } = require('../../utils/chineseConverter.js')

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

  // 执行搜索（支持简繁体）
  async onSearch() {
    const { keyword } = this.data
    
    if (!keyword || keyword.trim() === '') {
      wx.showToast({ title: '请输入关键词', icon: 'none' })
      return
    }

    this.setData({ searching: true })

    try {
      const kw = keyword.trim()
      // 生成简体和繁体两种变体，去重后并行搜索
      const variants = [...new Set([kw, toTraditional(kw), toSimplified(kw)])]
      const responses = await Promise.all(variants.map(v => api.searchEstates(v)))

      // 合并结果并按 id 去重
      const seenIds = new Set()
      const allResults = []
      responses.forEach(res => {
        if (res.success && res.data) {
          res.data.forEach(estate => {
            if (!seenIds.has(estate.id)) {
              seenIds.add(estate.id)
              allResults.push({
                ...estate,
                ratioColor: getRentRatioColor(
                  estate.rent_ratio,
                  this.data.minRatio,
                  this.data.maxRatio
                )
              })
            }
          })
        }
      })

      this.setData({
        results: allResults,
        searched: true,
        searching: false
      })
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
