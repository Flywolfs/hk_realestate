<template>
  <div class="color-legend">
    <h3>{{ isBuyRent ? '10年资产差图例' : '租售比图例' }}</h3>
    <div class="gradient-bar">
      <div 
        v-for="(color, index) in gradientColors" 
        :key="index"
        class="gradient-segment"
        :style="{ backgroundColor: color }"
      ></div>
    </div>
    <div class="legend-labels" v-if="isBuyRent">
      <span class="pivot-label">{{ formatWan(buyRentMin) }}</span>
      <span>0</span>
      <span class="pivot-label">{{ formatWan(buyRentMax) }}</span>
    </div>
    <div class="legend-labels" v-else>
      <span>0%</span>
      <span class="pivot-label">4%</span>
      <span>7%+</span>
    </div>
    <div class="legend-description" v-if="isBuyRent">
      <div class="desc-item">
        <span class="color-box green"></span>
        <span>绿：亏（租比买划算）</span>
      </div>
      <div class="desc-item">
        <span class="color-box red"></span>
        <span>红：赚（买比租划算）</span>
      </div>
      <div class="desc-item">
        <span>{{ spanDescription }}</span>
      </div>
    </div>
    <div class="legend-description" v-else>
      <div class="desc-item">
        <span class="color-box green"></span>
        <span>< 4%: 绿色渐变到黄色</span>
      </div>
      <div class="desc-item">
        <span class="color-box red"></span>
        <span>≥ 4%: 黄色渐变到红色</span>
      </div>
    </div>
    <div class="legend-note">
      <span class="gray-box"></span>
      <span>{{ isBuyRent ? '灰色 = 无评估数据' : '灰色 = 无租售比数据' }}</span>
    </div>
  </div>
</template>

<script>
import { getGradientColors, getBuyRentGradientColors, getBuyRentSpans, BUY_RENT_LEVELS_PER_SIDE } from '../utils/colorUtils.js'

export default {
  name: 'ColorLegend',
  props: {
    minValue: {
      type: Number,
      default: 0
    },
    maxValue: {
      type: Number,
      default: 10
    },
    // 买租资产差色带端点（负向 P5 / 正向 P95，null 时回退固定档位）
    buyRentMin: {
      type: Number,
      default: null
    },
    buyRentMax: {
      type: Number,
      default: null
    },
    // 视图模式：rentRatio=租售比 / buyRent=10年资产差
    mode: {
      type: String,
      default: 'rentRatio'
    }
  },
  computed: {
    isBuyRent() {
      return this.mode === 'buyRent'
    },
    gradientColors() {
      return this.isBuyRent ? getBuyRentGradientColors() : getGradientColors(20)
    },
    spanDescription() {
      const { negSpan, posSpan } = getBuyRentSpans(this.buyRentMin, this.buyRentMax)
      return `端点按 P5/P95 截断，正负各 ${BUY_RENT_LEVELS_PER_SIDE} 档：负向 ${this.formatSpan(negSpan)}/档，正向 ${this.formatSpan(posSpan)}/档`
    }
  },
  methods: {
    // 金额 → 万（带符号，大数取整，小数保留 1 位）
    formatWan(value) {
      if (value === null || value === undefined) return '-'
      const wan = value / 10000
      const digits = Math.abs(wan) >= 100 ? 0 : 1
      const sign = wan > 0 ? '+' : ''
      return sign + wan.toFixed(digits) + '万'
    },
    formatSpan(span) {
      const wan = span / 10000
      return (wan >= 100 ? wan.toFixed(0) : wan.toFixed(1)) + '万'
    }
  }
}
</script>

<style scoped>
.color-legend {
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

.color-legend h3 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #333;
}

.gradient-bar {
  display: flex;
  height: 20px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 5px;
}

.gradient-segment {
  flex: 1;
}

.legend-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
  margin-bottom: 10px;
  position: relative;
}

.pivot-label {
  font-weight: 600;
  color: #FF9800;
}

.legend-description {
  margin-bottom: 10px;
}

.desc-item {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: #666;
  margin-bottom: 5px;
  gap: 8px;
}

.color-box {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  display: inline-block;
}

.color-box.green {
  background: linear-gradient(to right, #5cb85c, #FFD700);
}

.color-box.red {
  background: linear-gradient(to right, #FFD700, #f44336);
}

.legend-note {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #666;
  gap: 8px;
}

.gray-box {
  width: 20px;
  height: 20px;
  background-color: #999999;
  border-radius: 3px;
  display: inline-block;
}
</style>
