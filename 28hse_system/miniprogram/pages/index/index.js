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
    filteredEstates: [], // 筛选后的小区数据
    
    // 统计数据
    estateCount: 0,
    avgRatio: 0,
    minRatio: 0,
    maxRatio: 10,
    filteredCount: 0,    // 过滤后的数量
    filteredAvgRatio: 0, // 过滤后的平均租售比
    
    // UI状态
    showStats: true,
    showLegend: false,
    loading: true,
    showFilterPanel: false, // 筛选面板显示状态
    
    // 点击的marker信息（用于显示浮窗）
    selectedEstate: null,
    showEstateCard: false,
    
    // 高亮的marker ID
    highlightedMarkerId: null,
    
    // 房屋类型筛选
    housingTypeFilter: {
      showPublic: true,    // 显示公屋
      showSubsidized: true, // 显示居屋
      showPrivate: true    // 显示私人屋苑
    },
    
    // 租售比区间筛选
    rentRatioFilter: {
      ranges: [
        { label: '<3%', value: 'lt3', min: 0, max: 3, selected: false },
        { label: '3%-3.5%', value: '3-3.5', min: 3, max: 3.5, selected: false },
        { label: '3.5%-4%', value: '3.5-4', min: 3.5, max: 4, selected: false },
        { label: '4%-5%', value: '4-5', min: 4, max: 5, selected: false },
        { label: '>5%', value: 'gt5', min: 5, max: 100, selected: false }
      ]
    },
    
    // 建成年份筛选
    yearFilter: {
      ranges: [
        { label: '2010年后', value: 'after2010', min: 2010, max: 2100, selected: false },
        { label: '2000-2010年', value: '2000-2010', min: 2000, max: 2010, selected: false },
        { label: '1990-2000年', value: '1990-2000', min: 1990, max: 2000, selected: false },
        { label: '1990年之前', value: 'before1990', min: 0, max: 1990, selected: false }
      ]
    },
    
    // 尺价筛选
    priceFilter: {
      targetPrice: '',  // 用户输入的目标尺价
      enabled: false    // 是否启用尺价筛选
    },
    
    // 是否有活跃筛选
    hasActiveFilter: false,
    
    // 登录弹窗显示状态
    showLoginModal: false
  },

  onLoad() {
    console.log('首页加载')
    // 页面加载时初始化
    this.loadRentRatioStats()
    this.loadEstates()
    
    // 检查是否需要显示登录弹窗（延迟2秒显示，避免打扰）
    setTimeout(() => {
      this.checkAndShowLoginModal()
    }, 2000)
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
    wx.showLoading({ title: '加载中... 0%' })
    try {
      // 先尝试从缓存读取（缓存的已是过滤+转换后的数据）
      const cachedEstates = getCache('all_estates_processed')
      if (cachedEstates) {
        console.log(`命中缓存，共 ${cachedEstates.length} 条屋苑`)
        this.setData({ 
          allEstates: cachedEstates,
          filteredEstates: cachedEstates,
          loading: false 
        })
        this.loadMarkersInView()
        wx.hideLoading()
        return
      }
  
      // 分页循环加载全量数据
      const res = await api.getAllEstates((loaded, total) => {
        const pct = Math.round(loaded / total * 100)
        wx.showLoading({ title: `加载中... ${pct}%` })
      })
  
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
  
        this.setData({ 
          allEstates: processedEstates,
          filteredEstates: processedEstates,
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
  async loadMarkersInView() {
    const { filteredEstates, centerLat, centerLng, scale, minRatio, maxRatio, highlightedMarkerId, selectedEstate } = this.data
    
    if (!filteredEstates || filteredEstates.length === 0) return
    
    // 根据scale计算可视范围
    const latRange = 1 / Math.pow(2, scale - 8)
    const lngRange = 1.5 / Math.pow(2, scale - 8)
    
    // 筛选可视区域内的小区
    const visibleEstates = filteredEstates.filter(estate => {
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
    
    // 检查当前高亮的屋苑是否仍在可视区域内
    let shouldClearHighlight = true
    if (highlightedMarkerId !== null && selectedEstate) {
      const highlightedEstateIndex = limitedEstates.findIndex(e => e.id === selectedEstate.estateId)
      if (highlightedEstateIndex !== -1) {
        shouldClearHighlight = false
      }
    }
    
    // 收集当前需要的所有颜色，预生成尚未缓存的图标
    const colors = [...new Set(limitedEstates.map(e => getRentRatioColor(e.rent_ratio, minRatio, maxRatio)))]
    await Promise.all(colors.map(c => this._getOrCreateIcon(c)))
    
    // 如果有高亮但屋苑不在可视区域，清除高亮状态
    if (shouldClearHighlight && highlightedMarkerId !== null) {
      this.setData({
        highlightedMarkerId: null,
        selectedEstate: null,
        showEstateCard: false
      })
    }
    
    // 构建 markers
    const markers = limitedEstates.map((estate, index) => {
      const color = getRentRatioColor(estate.rent_ratio, minRatio, maxRatio)
      const isHighlighted = !shouldClearHighlight && estate.id === selectedEstate.estateId
      const iconPath = this._iconCache[isHighlighted ? `${color}_highlight` : color] || ''
      
      return {
        id: index,
        latitude: estate.coordinates.latitude,
        longitude: estate.coordinates.longitude,
        iconPath,
        width: isHighlighted ? 28 : 22,
        height: isHighlighted ? 28 : 22,
        zIndex: isHighlighted ? 100 : 1,
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
  _getOrCreateIcon(color, isHighlighted = false) {
    if (!this._iconCache) this._iconCache = {}
    
    const cacheKey = isHighlighted ? `${color}_highlight` : color
    if (this._iconCache[cacheKey]) return Promise.resolve(this._iconCache[cacheKey])
    
    return new Promise((resolve) => {
      try {
        // 高亮状态使用更大的尺寸
        const baseSize = 44
        const size = isHighlighted ? 56 : baseSize
        const canvas = wx.createOffscreenCanvas({ type: '2d', width: size, height: size })
        const ctx = canvas.getContext('2d')
        
        ctx.clearRect(0, 0, size, size)
        
        if (isHighlighted) {
          // 高亮状态：外圈发光效果
          ctx.beginPath()
          ctx.arc(size / 2, size / 2, size / 2 - 1, 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(102, 126, 234, 0.3)'  // 紫色发光
          ctx.fill()
          
          // 白色外圈
          ctx.beginPath()
          ctx.arc(size / 2, size / 2, size / 2 - 4, 0, 2 * Math.PI)
          ctx.fillStyle = '#fff'
          ctx.fill()
          
          // 彩色内圆（更大）
          ctx.beginPath()
          ctx.arc(size / 2, size / 2, size / 2 - 10, 0, 2 * Math.PI)
          ctx.fillStyle = color
          ctx.fill()
          
          // 中心白点
          ctx.beginPath()
          ctx.arc(size / 2, size / 2, size / 2 - 18, 0, 2 * Math.PI)
          ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
          ctx.fill()
        } else {
          // 普通状态
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
        }
        
        wx.canvasToTempFilePath({
          canvas,
          success: (res) => {
            this._iconCache[cacheKey] = res.tempFilePath
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
    // 只在用户操作结束时触发更新（包括拖拽和缩放）
    if (e.type === 'end' && (e.causedBy === 'drag' || e.causedBy === 'scale')) {
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
  async onMarkerTap(e) {
    const markerId = e.detail.markerId
    const marker = this.data.markers[markerId]
    if (marker && marker.customData) {
      // 先清除之前的高亮
      const previousHighlightedId = this.data.highlightedMarkerId
      
      // 获取该marker的颜色并生成高亮图标
      const color = marker.customData.rentRatio ? 
        getRentRatioColor(marker.customData.rentRatio, this.data.minRatio, this.data.maxRatio) : 
        '#999'
      
      // 预生成高亮图标
      await this._getOrCreateIcon(color, true)
      
      // 更新高亮状态
      this.setData({
        selectedEstate: marker.customData,
        showEstateCard: true,
        highlightedMarkerId: markerId
      })
      
      // 更新markers以显示高亮效果
      this.updateMarkerHighlight(markerId, previousHighlightedId)
    }
  },
  
  // 更新marker高亮状态
  updateMarkerHighlight(newHighlightedId, previousHighlightedId) {
    const { markers, minRatio, maxRatio } = this.data
    
    const updatedMarkers = markers.map((marker, index) => {
      const isHighlighted = index === newHighlightedId
      const wasHighlighted = index === previousHighlightedId
      
      // 只有状态变化的marker才需要更新
      if (!isHighlighted && !wasHighlighted) {
        return marker
      }
      
      const color = marker.customData.rentRatio ? 
        getRentRatioColor(marker.customData.rentRatio, minRatio, maxRatio) : 
        '#999'
      
      const iconPath = this._iconCache[isHighlighted ? `${color}_highlight` : color] || ''
      
      return {
        ...marker,
        iconPath,
        width: isHighlighted ? 28 : 22,  // 高亮时更大
        height: isHighlighted ? 28 : 22,
        zIndex: isHighlighted ? 100 : 1   // 高亮时在最上层
      }
    })
    
    this.setData({ markers: updatedMarkers })
  },
  
  // 清除marker高亮
  clearMarkerHighlight() {
    const { markers, minRatio, maxRatio, highlightedMarkerId } = this.data
    
    if (highlightedMarkerId === null) return
    
    const updatedMarkers = markers.map((marker) => {
      const color = marker.customData.rentRatio ? 
        getRentRatioColor(marker.customData.rentRatio, minRatio, maxRatio) : 
        '#999'
      
      const iconPath = this._iconCache[color] || ''
      
      return {
        ...marker,
        iconPath,
        width: 22,
        height: 22,
        zIndex: 1
      }
    })
    
    this.setData({ 
      markers: updatedMarkers,
      highlightedMarkerId: null
    })
  },
  
  // 关闭信息卡片
  closeEstateCard() {
    this.setData({
      showEstateCard: false,
      selectedEstate: null
    })
    // 清除高亮
    this.clearMarkerHighlight()
  },
  
  // 查看详情
  viewEstateDetail() {
    const { selectedEstate } = this.data
    if (selectedEstate) {
      // 清除高亮状态
      this.clearMarkerHighlight()
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
  },

  // 分享到朋友圈
  onShareTimeline() {
    return {
      title: '香港小区租售比地图',
      query: '',
      imageUrl: ''  // 可以设置分享图片，建议 5:4 比例
    }
  },

  // 切换房屋类型筛选
  toggleHousingType(type) {
    const { housingTypeFilter, allEstates } = this.data
    const newFilter = { ...housingTypeFilter }
    
    // 切换对应类型的显示状态
    if (type === 'public') {
      newFilter.showPublic = !newFilter.showPublic
    } else if (type === 'subsidized') {
      newFilter.showSubsidized = !newFilter.showSubsidized
    } else if (type === 'private') {
      newFilter.showPrivate = !newFilter.showPrivate
    }
    
    // 先应用房屋类型筛选
    let filteredEstates = allEstates.filter(estate => {
      const housingType = estate.housing_type
      
      // gongwu = 公屋, juwu = 居屋, null = 私人屋苑
      if (housingType === 'gongwu') {
        return newFilter.showPublic
      } else if (housingType === 'juwu') {
        return newFilter.showSubsidized
      } else {
        // null 或其他值视为私人屋苑
        return newFilter.showPrivate
      }
    })
    
    // 再应用其他筛选条件
    filteredEstates = this.applyFilters(filteredEstates)
    
    this.setData({
      housingTypeFilter: newFilter,
      filteredEstates: filteredEstates
    })
    
    // 更新过滤后的统计数据
    this.updateFilteredStats(filteredEstates)
    
    // 重新加载地图标记
    this.loadMarkersInView()
    
    // 显示提示
    const typeName = type === 'public' ? '公屋' : (type === 'subsidized' ? '居屋' : '私人屋苑')
    const action = newFilter[type === 'public' ? 'showPublic' : (type === 'subsidized' ? 'showSubsidized' : 'showPrivate')] ? '显示' : '隐藏'
    wx.showToast({
      title: `${action}${typeName}`,
      icon: 'none',
      duration: 1500
    })
  },

  // 切换公屋显示
  togglePublic() {
    this.toggleHousingType('public')
  },

  // 切换居屋显示
  toggleSubsidized() {
    this.toggleHousingType('subsidized')
  },

  // 切换私人屋苑显示
  togglePrivate() {
    this.toggleHousingType('private')
  },

  // ========== 筛选面板相关方法 ==========
  
  // 显示/隐藏筛选面板
  toggleFilterPanel() {
    this.setData({ showFilterPanel: !this.data.showFilterPanel })
  },
  
  hideFilterPanel() {
    this.setData({ showFilterPanel: false })
  },
  
  // 阻止事件冒泡
  preventClose() {},
  
  // 切换租售比区间选择
  toggleRentRatioRange(e) {
    const { index } = e.currentTarget.dataset
    const { rentRatioFilter } = this.data
    const newRanges = [...rentRatioFilter.ranges]
    newRanges[index].selected = !newRanges[index].selected
    
    this.setData({
      'rentRatioFilter.ranges': newRanges
    })
  },
  
  // 切换建成年份区间选择
  toggleYearRange(e) {
    const { index } = e.currentTarget.dataset
    const { yearFilter } = this.data
    const newRanges = [...yearFilter.ranges]
    newRanges[index].selected = !newRanges[index].selected
    
    this.setData({
      'yearFilter.ranges': newRanges
    })
  },
  
  // 输入目标尺价
  onPriceInput(e) {
    const value = e.detail.value
    this.setData({
      'priceFilter.targetPrice': value
    })
  },
  
  // 切换尺价筛选启用状态
  togglePriceFilter() {
    const { priceFilter } = this.data
    this.setData({
      'priceFilter.enabled': !priceFilter.enabled
    })
  },
  
  // 应用所有筛选条件
  applyAllFilters() {
    const { allEstates, housingTypeFilter } = this.data
    
    // 先应用房屋类型筛选
    let filteredEstates = allEstates.filter(estate => {
      const housingType = estate.housing_type
      if (housingType === 'gongwu') {
        return housingTypeFilter.showPublic
      } else if (housingType === 'juwu') {
        return housingTypeFilter.showSubsidized
      } else {
        return housingTypeFilter.showPrivate
      }
    })
    
    // 再应用其他筛选条件
    filteredEstates = this.applyFilters(filteredEstates)
    
    // 检查是否有活跃筛选
    const hasActiveFilter = this.checkHasActiveFilter()
    
    this.setData({
      filteredEstates: filteredEstates,
      hasActiveFilter: hasActiveFilter,
      showFilterPanel: false
    })
    
    // 更新过滤后的统计数据
    this.updateFilteredStats(filteredEstates)
    
    // 重新加载地图标记
    this.loadMarkersInView()
    
    // 显示结果提示
    wx.showToast({
      title: `筛选完成，共${filteredEstates.length}个屋苑`,
      icon: 'none',
      duration: 2000
    })
  },
  
  // 清除所有筛选条件
  clearAllFilters() {
    const { rentRatioFilter, yearFilter, priceFilter } = this.data
    
    // 重置租售比筛选
    const newRentRatioRanges = rentRatioFilter.ranges.map(r => ({ ...r, selected: false }))
    
    // 重置年份筛选
    const newYearRanges = yearFilter.ranges.map(r => ({ ...r, selected: false }))
    
    this.setData({
      'rentRatioFilter.ranges': newRentRatioRanges,
      'yearFilter.ranges': newYearRanges,
      'priceFilter.targetPrice': '',
      'priceFilter.enabled': false,
      hasActiveFilter: false
    })
    
    // 重新应用房屋类型筛选
    this.applyHousingTypeFilterOnly()
    
    wx.showToast({
      title: '已清除所有筛选',
      icon: 'success',
      duration: 1500
    })
  },
  
  // 仅应用房屋类型筛选（用于清除其他筛选时）
  applyHousingTypeFilterOnly() {
    const { allEstates, housingTypeFilter } = this.data
    
    const filteredEstates = allEstates.filter(estate => {
      const housingType = estate.housing_type
      if (housingType === 'gongwu') {
        return housingTypeFilter.showPublic
      } else if (housingType === 'juwu') {
        return housingTypeFilter.showSubsidized
      } else {
        return housingTypeFilter.showPrivate
      }
    })
    
    this.setData({
      filteredEstates: filteredEstates,
      showFilterPanel: false
    })
    
    // 更新过滤后的统计数据
    this.updateFilteredStats(filteredEstates)
    
    // 重新加载地图标记
    this.loadMarkersInView()
  },
  
  // 应用筛选条件到数据集
  applyFilters(estates) {
    const { rentRatioFilter, yearFilter, priceFilter } = this.data
    
    // 检查是否有租售比筛选
    const selectedRatioRanges = rentRatioFilter.ranges.filter(r => r.selected)
    const hasRatioFilter = selectedRatioRanges.length > 0
    
    // 检查是否有年份筛选
    const selectedYearRanges = yearFilter.ranges.filter(r => r.selected)
    const hasYearFilter = selectedYearRanges.length > 0
    
    // 检查是否有尺价筛选
    const hasPriceFilter = priceFilter.enabled && priceFilter.targetPrice
    const targetPrice = hasPriceFilter ? parseFloat(priceFilter.targetPrice) : 0
    
    return estates.filter(estate => {
      // 租售比筛选
      if (hasRatioFilter) {
        const ratio = estate.rent_ratio
        if (ratio === null || ratio === undefined) return false
        const matchRatio = selectedRatioRanges.some(range => 
          ratio >= range.min && ratio < range.max
        )
        if (!matchRatio) return false
      }
      
      // 年份筛选
      if (hasYearFilter) {
        const year = estate.establish_year
        if (!year) return false
        const matchYear = selectedYearRanges.some(range => 
          year >= range.min && year < range.max
        )
        if (!matchYear) return false
      }
      
      // 尺价筛选 - 显示尺价在目标值±20%范围内的屋苑
      if (hasPriceFilter) {
        const price = estate.current_price_per_sqft
        if (!price) return false
        const tolerance = targetPrice * 0.05  // ±20%容差
        if (price < targetPrice - tolerance || price > targetPrice + tolerance) {
          return false
        }
      }
      
      return true
    })
  },
  
  // 检查是否有活跃筛选
  checkHasActiveFilter() {
    const { rentRatioFilter, yearFilter, priceFilter } = this.data
    const hasRatioFilter = rentRatioFilter.ranges.some(r => r.selected)
    const hasYearFilter = yearFilter.ranges.some(r => r.selected)
    const hasPriceFilter = priceFilter.enabled && priceFilter.targetPrice
    return hasRatioFilter || hasYearFilter || hasPriceFilter
  },
  
  // 更新过滤后的统计数据
  updateFilteredStats(filteredEstates) {
    const count = filteredEstates.length
    let avgRatio = 0
    
    if (count > 0) {
      const totalRatio = filteredEstates.reduce((sum, estate) => {
        return sum + (estate.rent_ratio || 0)
      }, 0)
      avgRatio = (totalRatio / count).toFixed(2)
    }
    
    this.setData({
      filteredCount: count,
      filteredAvgRatio: avgRatio
    })
  },

  // ========== 登录相关方法 ==========
  
  // 检查并显示登录弹窗
  checkAndShowLoginModal() {
    const app = getApp()
    // 如果用户未登录，且今天还没有提示过，则显示登录弹窗
    if (!app.globalData.isLoggedIn) {
      const lastPromptDate = wx.getStorageSync('last_login_prompt_date')
      const today = new Date().toDateString()
      
      // 每天只提示一次
      if (lastPromptDate !== today) {
        this.setData({ showLoginModal: true })
      }
    }
  },
  
  // 关闭登录弹窗
  closeLoginModal() {
    this.setData({ showLoginModal: false })
  },
  
  // 处理登录
  handleLogin(e) {
    const app = getApp()
    
    // 从 button 的 getuserinfo 事件获取用户信息
    let userInfo = {}
    if (e.detail && e.detail.userInfo) {
      userInfo = e.detail.userInfo
      console.log('获取到用户信息:', userInfo.nickName)
    } else {
      console.log('用户未授权获取信息，将进行匿名登录')
    }
    
    wx.showLoading({ title: '登录中...' })
    
    // 传入用户信息（可能为空）
    app.doLogin(userInfo).then(res => {
      wx.hideLoading()
      
      // 记录今天已提示
      wx.setStorageSync('last_login_prompt_date', new Date().toDateString())
      
      this.setData({ showLoginModal: false })
      
      wx.showToast({
        title: '登录成功',
        icon: 'success'
      })
      
      console.log('用户登录成功:', res.userInfo)
    }).catch(err => {
      wx.hideLoading()
      console.error('登录失败:', err)
      wx.showToast({
        title: '登录失败，请重试',
        icon: 'none'
      })
    })
  },
  
  // 以游客身份继续
  continueAsGuest() {
    // 记录今天已提示，今天不再显示
    wx.setStorageSync('last_login_prompt_date', new Date().toDateString())
    this.setData({ showLoginModal: false })
  }
})
