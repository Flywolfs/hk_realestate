<template>
  <div class="color-legend">
    <h3>租售比图例</h3>
    <div class="gradient-bar">
      <div 
        v-for="(color, index) in gradientColors" 
        :key="index"
        class="gradient-segment"
        :style="{ backgroundColor: color }"
      ></div>
    </div>
    <div class="legend-labels">
      <span>0%</span>
      <span class="pivot-label">4%</span>
      <span>7%+</span>
    </div>
    <div class="legend-description">
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
      <span>灰色 = 无租售比数据</span>
    </div>
  </div>
</template>

<script>
import { getGradientColors } from '../utils/colorUtils.js'

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
    }
  },
  computed: {
    gradientColors() {
      return getGradientColors(20)
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
