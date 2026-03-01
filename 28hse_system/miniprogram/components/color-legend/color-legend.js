// components/color-legend/color-legend.js
const { getGradientColors } = require('../../utils/colorUtils.js')

Component({
  properties: {
    minValue: {
      type: Number,
      value: 0
    },
    maxValue: {
      type: Number,
      value: 10
    }
  },
  
  data: {
    colors: []
  },
  
  lifetimes: {
    attached() {
      // 生成渐变色数组
      this.setData({
        colors: getGradientColors(10)
      })
    }
  },
  
  methods: {
    onClose() {
      this.triggerEvent('close')
    }
  }
})
