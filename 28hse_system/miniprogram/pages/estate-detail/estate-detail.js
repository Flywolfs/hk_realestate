// pages/estate-detail/estate-detail.js - 小区详情页
const api = require('../../utils/api.js')
const { getRentRatioColor } = require('../../utils/colorUtils.js')

Page({
  data: {
    estate: null,
    loading: true,
    ratioColor: '#999',
    minRatio: 0,
    maxRatio: 10,
    hasTrendData: false,
    hasRoomTypeRatio: false,
    roomTypeRatioList: [],
    hasPriceTrendData: false,
    trendCanvasWidth: 0,
    trendCanvasHeight: 0,
    // 趋势图选中点
    selectedPoint: null,
    // 尺价趋势图选中点
    selectedPricePoint: null,
    // 水印列表
    watermarkList: []
  },

  onLoad(options) {
    const estateId = options.id
    if (estateId) {
      this.loadEstateDetail(estateId)
      this.loadRatioRange()
      this.generateWatermark()
    }
  },

  // 生成水印
  generateWatermark() {
    const watermarkText = '港房Data'
    const rows = 6
    const cols = 4
    const watermarkList = []
    
    // 获取系统信息计算屏幕尺寸
    const sysInfo = wx.getSystemInfoSync()
    const screenWidth = sysInfo.windowWidth
    const screenHeight = sysInfo.windowHeight
    
    // 将像素转换为 rpx (750rpx = screenWidth px)
    const rpxRatio = 750 / screenWidth
    
    const cellWidth = 750 / cols
    const cellHeight = (screenHeight * rpxRatio) / rows
    
    // 固定旋转角度 -30度
    const fixedRotate = -30
    
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        // 添加随机偏移，使水印分布更自然，但旋转角度固定
        const offsetX = Math.random() * 40 - 20
        const offsetY = Math.random() * 40 - 20
        
        watermarkList.push({
          text: watermarkText,
          x: col * cellWidth + cellWidth / 2 + offsetX,
          y: row * cellHeight + cellHeight / 2 + offsetY,
          rotate: fixedRotate
        })
      }
    }
    
    this.setData({ watermarkList })
  },

  onShow() {
    // 页面显示时重新绘制图表（处理从地图返回的情况）
    if (this.data.hasTrendData) {
      setTimeout(() => {
        this.drawTrendChart()
      }, 300)
    }
    if (this.data.hasPriceTrendData) {
      setTimeout(() => {
        this.drawPriceTrendChart()
      }, 300)
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

  // 处理户型租售比数据
  processRoomTypeRatio(roomTypeRatioData) {
    const { minRatio, maxRatio } = this.data
    const { getRentRatioColor } = require('../../utils/colorUtils.js')

    // 户型标签映射
    const roomTypeLabels = {
      '1': '开放式/一房',
      '2': '两房',
      '3': '三房',
      '4': '四房及以上'
    }

    return Object.entries(roomTypeRatioData)
      .map(([roomType, ratio]) => {
        // 判断户型类型（按面积或房间数）
        let label = ''
        if (roomTypeLabels[roomType]) {
          label = roomTypeLabels[roomType]
        } else if (!isNaN(parseInt(roomType))) {
          const area = parseInt(roomType)
          if (area < 300) label = '小户型'
          else if (area < 600) label = '中户型'
          else if (area < 1000) label = '大户型'
          else label = '豪宅'
        } else {
          label = '其他'
        }

        return {
          roomType: roomType,
          ratio: parseFloat(ratio).toFixed(2),
          label: label,
          color: getRentRatioColor(ratio, minRatio, maxRatio)
        }
      })
      .sort((a, b) => parseFloat(b.ratio) - parseFloat(a.ratio)) // 按租售比降序排列
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
        
        // 检查是否有租售比趋势数据
        const hasTrendData = res.data.overall_ratio_timeseries &&
          Object.keys(res.data.overall_ratio_timeseries).length > 0

        // 检查是否有尺价趋势数据
        const hasPriceTrendData = res.data.price_trend_timeseries &&
          Object.keys(res.data.price_trend_timeseries).length > 0

        // 处理户型租售比数据
        const roomTypeRatioData = res.data.room_type_ratio || {}
        const hasRoomTypeRatio = Object.keys(roomTypeRatioData).length > 0
        const roomTypeRatioList = this.processRoomTypeRatio(roomTypeRatioData)

        this.setData({
          estate: res.data,
          loading: false,
          ratioColor: color,
          hasTrendData: hasTrendData,
          hasRoomTypeRatio: hasRoomTypeRatio,
          roomTypeRatioList: roomTypeRatioList,
          hasPriceTrendData: hasPriceTrendData
        })
        
        // 如果有租售比趋势数据，等待页面渲染后绘制图表
        if (hasTrendData) {
          setTimeout(() => {
            this.drawTrendChart()
          }, 300)
        }
        
        // 如果有尺价趋势数据，等待页面渲染后绘制图表
        if (hasPriceTrendData) {
          setTimeout(() => {
            this.drawPriceTrendChart()
          }, 300)
        }
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
  },

  // 分享到朋友圈
  onShareTimeline() {
    const { estate } = this.data
    return {
      title: `${estate.name} - 租售比${estate.rent_ratio}%`,
      query: `id=${estate.id}`,
      imageUrl: ''  // 可以设置屋苑图片，建议 5:4 比例
    }
  },

  // 绘制租售比趋势图
  drawTrendChart() {
    const { estate, minRatio, maxRatio } = this.data
    if (!estate || !estate.overall_ratio_timeseries) {
      return
    }

    const timeseries = estate.overall_ratio_timeseries
    // 将字典转换为排序后的数组
    const sortedDates = Object.keys(timeseries).sort()
    
    if (sortedDates.length === 0) {
      return
    }

    const values = sortedDates.map(date => timeseries[date])
    const _this = this
    
    // 计算画布尺寸
    const query = wx.createSelectorQuery()
    query.select('#trendCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0]) return
        
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio
        
        const width = res[0].width
        const height = res[0].height
        
        canvas.width = width * dpr
        canvas.height = height * dpr
        ctx.scale(dpr, dpr)

        // 设置背景
        ctx.fillStyle = '#f8f8f8'
        ctx.fillRect(0, 0, width, height)

        // 计算数据范围
        const dataMin = Math.min(...values)
        const dataMax = Math.max(...values)
        const padding = { top: 40, right: 20, bottom: 50, left: 50 }
        const chartWidth = width - padding.left - padding.right
        const chartHeight = height - padding.top - padding.bottom

        // 计算Y轴范围（确保有合理显示范围）
        const yMin = Math.max(0, Math.floor(dataMin - 1))
        const yMax = Math.ceil(dataMax + 1)

        // 绘制Y轴网格线和标签
        ctx.strokeStyle = '#e0e0e0'
        ctx.fillStyle = '#666'
        ctx.font = '22rpx sans-serif'
        ctx.textAlign = 'right'
        ctx.textBaseline = 'middle'

        const yStep = (yMax - yMin) / 5
        for (let i = 0; i <= 5; i++) {
          const y = padding.top + (chartHeight / 5) * i
          const value = yMax - (yStep * i)
          
          // 网格线
          ctx.beginPath()
          ctx.moveTo(padding.left, y)
          ctx.lineTo(width - padding.right, y)
          ctx.stroke()
          
          // Y轴标签
          ctx.fillText(value.toFixed(1) + '%', padding.left - 10, y)
        }

        // 绘制X轴标签
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const xStep = Math.ceil(sortedDates.length / 6) || 1
        let lastYear = null
        sortedDates.forEach((date, index) => {
          if (index % xStep === 0 || index === sortedDates.length - 1) {
            const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
            const year = date.substring(0, 4)
            const monthDay = date.substring(5) // MM-DD
            // 年份变化时显示年份，否则只显示月-日
            const labelText = (year !== lastYear) ? `${year}-${monthDay}` : monthDay
            lastYear = year
            ctx.fillText(labelText, x, height - padding.bottom + 10)
          }
        })

        // 绘制折线
        const { getRentRatioColor } = require('../../utils/colorUtils.js')
        
        ctx.beginPath()
        ctx.strokeStyle = '#4CAF50'
        ctx.lineWidth = 3
        ctx.lineJoin = 'round'

        sortedDates.forEach((date, index) => {
          const value = timeseries[date]
          const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
          const y = padding.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight

          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()

        // 绘制数据点
        const pointPositions = []
        sortedDates.forEach((date, index) => {
          const value = timeseries[date]
          const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
          const y = padding.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight
          
          // 保存点的位置用于点击检测
          pointPositions.push({ x, y, value, date })
          
          // 获取点的颜色
          const pointColor = getRentRatioColor(value, minRatio, maxRatio)
          
          ctx.beginPath()
          ctx.arc(x, y, 5, 0, 2 * Math.PI)
          ctx.fillStyle = pointColor
          ctx.fill()
          ctx.strokeStyle = '#fff'
          ctx.lineWidth = 2
          ctx.stroke()
        })

        // 绘制标题
        ctx.fillStyle = '#333'
        ctx.font = 'bold 26rpx sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('租售比变化趋势', width / 2, 20)

        // 保存点的位置供触摸事件使用
        this.pointPositions = pointPositions
      })
  },

  // Canvas触摸开始事件
  onCanvasTouchStart(e) {
    const touch = e.touches[0]
    const pointPositions = this.pointPositions || []
    
    if (pointPositions.length === 0) return
    
    // 获取Canvas在页面中的位置
    const query = wx.createSelectorQuery()
    query.select('#trendCanvas').boundingClientRect()
    query.exec((res) => {
      if (!res[0]) return
      
      const rect = res[0]
      const clickX = touch.clientX - rect.left
      const clickY = touch.clientY - rect.top
      
      // 查找最近的数据点
      let minDist = Infinity
      let closestPoint = null
      
      pointPositions.forEach(point => {
        const dist = Math.sqrt(Math.pow(clickX - point.x, 2) + Math.pow(clickY - point.y, 2))
        if (dist < minDist && dist < 40) {
          minDist = dist
          closestPoint = point
        }
      })
      
      if (closestPoint) {
        // 确保数值正确转换为数字
        const pointValue = parseFloat(closestPoint.value)
        
        // 计算提示框位置，避免超出边界
        // Canvas 宽度约为 750rpx (100%)，高度为 400rpx
        const canvasWidth = 750  // rpx
        const canvasHeight = 400 // rpx
        const tooltipWidth = 160  // 提示框估算宽度 rpx
        const tooltipHeight = 100 // 提示框估算高度 rpx
        
        let tooltipX = closestPoint.x
        let tooltipY = closestPoint.y - 20 // 默认在点上方
        let tooltipPosition = 'top' // top, bottom, left, right
        
        // 检查上方空间是否足够
        if (tooltipY < tooltipHeight) {
          // 上方空间不足，显示在点下方
          tooltipY = closestPoint.y + 20
          tooltipPosition = 'bottom'
        }
        
        // 检查左右边界
        if (tooltipX < tooltipWidth / 2) {
          // 太靠左，调整X位置
          tooltipX = tooltipWidth / 2 + 10
        } else if (tooltipX > canvasWidth - tooltipWidth / 2) {
          // 太靠右，调整X位置
          tooltipX = canvasWidth - tooltipWidth / 2 - 10
        }
        
        this.setData({
          selectedPoint: {
            x: tooltipX,
            y: tooltipY,
            value: pointValue,
            date: closestPoint.date,
            position: tooltipPosition
          }
        })
      } else {
        this.setData({
          selectedPoint: null
        })
      }
    })
  },

  // Canvas触摸结束事件
  onCanvasTouchEnd() {
    this.setData({
      selectedPoint: null
    })
  },

  // 绘制尺价趋势图
  drawPriceTrendChart() {
    const { estate } = this.data
    if (!estate || !estate.price_trend_timeseries) {
      return
    }

    const timeseries = estate.price_trend_timeseries
    // 将字典转换为排序后的数组
    const sortedDates = Object.keys(timeseries).sort()
    
    if (sortedDates.length === 0) {
      return
    }

    const values = sortedDates.map(date => timeseries[date])
    
    // 计算画布尺寸
    const query = wx.createSelectorQuery()
    query.select('#priceTrendCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
        if (!res[0]) return
        
        const canvas = res[0].node
        const ctx = canvas.getContext('2d')
        const dpr = wx.getSystemInfoSync().pixelRatio
        
        const width = res[0].width
        const height = res[0].height
        
        canvas.width = width * dpr
        canvas.height = height * dpr
        ctx.scale(dpr, dpr)

        // 设置背景
        ctx.fillStyle = '#f8f8f8'
        ctx.fillRect(0, 0, width, height)

        // 计算数据范围
        const dataMin = Math.min(...values)
        const dataMax = Math.max(...values)
        const padding = { top: 40, right: 20, bottom: 50, left: 60 }
        const chartWidth = width - padding.left - padding.right
        const chartHeight = height - padding.top - padding.bottom

        // 计算Y轴范围（确保有合理显示范围）
        const yMin = Math.floor(dataMin * 0.95)
        const yMax = Math.ceil(dataMax * 1.05)

        // 绘制Y轴网格线和标签
        ctx.strokeStyle = '#e0e0e0'
        ctx.fillStyle = '#666'
        ctx.font = '22rpx sans-serif'
        ctx.textAlign = 'right'
        ctx.textBaseline = 'middle'

        const yStep = (yMax - yMin) / 5
        for (let i = 0; i <= 5; i++) {
          const y = padding.top + (chartHeight / 5) * i
          const value = yMax - (yStep * i)
          
          // 网格线
          ctx.beginPath()
          ctx.moveTo(padding.left, y)
          ctx.lineTo(width - padding.right, y)
          ctx.stroke()
          
          // Y轴标签
          ctx.fillText('$' + Math.round(value), padding.left - 10, y)
        }

        // 绘制X轴标签
        ctx.textAlign = 'center'
        ctx.textBaseline = 'top'
        const xStep = Math.ceil(sortedDates.length / 6) || 1
        let lastYear = null
        sortedDates.forEach((date, index) => {
          if (index % xStep === 0 || index === sortedDates.length - 1) {
            const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
            const year = date.substring(0, 4)
            const monthDay = date.substring(5) // MM-DD
            // 年份变化时显示年份，否则只显示月-日
            const labelText = (year !== lastYear) ? `${year}-${monthDay}` : monthDay
            lastYear = year
            ctx.fillText(labelText, x, height - padding.bottom + 10)
          }
        })

        // 绘制折线
        ctx.beginPath()
        ctx.strokeStyle = '#2196F3'
        ctx.lineWidth = 3
        ctx.lineJoin = 'round'

        sortedDates.forEach((date, index) => {
          const value = timeseries[date]
          const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
          const y = padding.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight

          if (index === 0) {
            ctx.moveTo(x, y)
          } else {
            ctx.lineTo(x, y)
          }
        })
        ctx.stroke()

        // 绘制数据点
        const pointPositions = []
        sortedDates.forEach((date, index) => {
          const value = timeseries[date]
          const x = padding.left + (chartWidth / (sortedDates.length - 1 || 1)) * index
          const y = padding.top + chartHeight - ((value - yMin) / (yMax - yMin)) * chartHeight
          
          // 保存点的位置用于点击检测
          pointPositions.push({ x, y, value, date })
          
          ctx.beginPath()
          ctx.arc(x, y, 5, 0, 2 * Math.PI)
          ctx.fillStyle = '#2196F3'
          ctx.fill()
          ctx.strokeStyle = '#fff'
          ctx.lineWidth = 2
          ctx.stroke()
        })

        // 绘制标题
        ctx.fillStyle = '#333'
        ctx.font = 'bold 26rpx sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('尺价变化趋势', width / 2, 20)

        // 保存点的位置供触摸事件使用
        this.pricePointPositions = pointPositions
      })
  },

  // 尺价趋势图Canvas触摸开始事件
  onPriceCanvasTouchStart(e) {
    const touch = e.touches[0]
    const pointPositions = this.pricePointPositions || []
    
    if (pointPositions.length === 0) return
    
    // 获取Canvas在页面中的位置
    const query = wx.createSelectorQuery()
    query.select('#priceTrendCanvas').boundingClientRect()
    query.exec((res) => {
      if (!res[0]) return
      
      const rect = res[0]
      const clickX = touch.clientX - rect.left
      const clickY = touch.clientY - rect.top
      
      // 查找最近的数据点
      let minDist = Infinity
      let closestPoint = null
      
      pointPositions.forEach(point => {
        const dist = Math.sqrt(Math.pow(clickX - point.x, 2) + Math.pow(clickY - point.y, 2))
        if (dist < minDist && dist < 40) {
          minDist = dist
          closestPoint = point
        }
      })
      
      if (closestPoint) {
        // 确保数值正确转换为数字
        const pointValue = parseFloat(closestPoint.value)
        
        // 计算提示框位置，避免超出边界
        const canvasWidth = 750  // rpx
        const tooltipWidth = 180  // 提示框估算宽度 rpx
        const tooltipHeight = 100 // 提示框估算高度 rpx
        
        let tooltipX = closestPoint.x
        let tooltipY = closestPoint.y - 20 // 默认在点上方
        let tooltipPosition = 'top' // top, bottom, left, right
        
        // 检查上方空间是否足够
        if (tooltipY < tooltipHeight) {
          // 上方空间不足，显示在点下方
          tooltipY = closestPoint.y + 20
          tooltipPosition = 'bottom'
        }
        
        // 检查左右边界
        if (tooltipX < tooltipWidth / 2) {
          tooltipX = tooltipWidth / 2 + 10
        } else if (tooltipX > canvasWidth - tooltipWidth / 2) {
          tooltipX = canvasWidth - tooltipWidth / 2 - 10
        }
        
        this.setData({
          selectedPricePoint: {
            x: tooltipX,
            y: tooltipY,
            value: pointValue,
            date: closestPoint.date,
            position: tooltipPosition
          }
        })
      } else {
        this.setData({
          selectedPricePoint: null
        })
      }
    })
  },

  // 尺价趋势图Canvas触摸结束事件
  onPriceCanvasTouchEnd() {
    this.setData({
      selectedPricePoint: null
    })
  }
})
