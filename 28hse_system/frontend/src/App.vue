<template>
  <div class="app-container">
    <div class="sidebar">
      <div class="header">
        <h1>香港小区租售比地图</h1>
        <p class="subtitle">Hong Kong Rent-Sale Ratio Map</p>
      </div>
      
      <!-- 指标切换开关 -->
      <div class="view-switch">
        <button
          class="switch-btn"
          :class="{ active: viewMode === 'rentRatio' }"
          @click="viewMode = 'rentRatio'"
        >租售比</button>
        <button
          class="switch-btn"
          :class="{ active: viewMode === 'buyRent' }"
          @click="viewMode = 'buyRent'"
        >10年资产差</button>
      </div>
      
      <SearchBar @select-estate="handleEstateSelect" />
      
      <ColorLegend 
        :min-value="rentRatioMin" 
        :max-value="rentRatioMax" 
        :mode="viewMode"
      />
      
      <div class="stats-panel">
        <h3>数据统计</h3>
        <template v-if="viewMode === 'rentRatio'">
          <div class="stat-item">
            <span class="stat-label">小区总数:</span>
            <span class="stat-value">{{ estateCount }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">平均租售比:</span>
            <span class="stat-value">{{ rentRatioAvg }}%</span>
          </div>
        </template>
        <template v-else>
          <div class="stat-item">
            <span class="stat-label">评估覆盖屋苑:</span>
            <span class="stat-value">{{ buyRentStats ? buyRentStats.count : '-' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">值得买屋苑:</span>
            <span class="stat-value">{{ buyRentStats ? buyRentStats.buy_count : '-' }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">资产差中位数:</span>
            <span class="stat-value">{{ buyRentMedianText }}</span>
          </div>
        </template>
      </div>
    </div>
    
    <div class="map-area">
      <MapView ref="mapView" :view-mode="viewMode" @data-loaded="handleDataLoaded" />
    </div>
  </div>
</template>

<script>
import MapView from './components/MapView.vue'
import SearchBar from './components/SearchBar.vue'
import ColorLegend from './components/ColorLegend.vue'
import { getRentRatioStats, getBuyRentStats } from './utils/api.js'

export default {
  name: 'App',
  components: {
    MapView,
    SearchBar,
    ColorLegend
  },
  data() {
    return {
      // 视图模式：rentRatio=租售比 / buyRent=10年资产差
      viewMode: 'rentRatio',
      rentRatioMin: 0,
      rentRatioMax: 10,
      rentRatioAvg: 0,
      estateCount: 0,
      buyRentStats: null
    }
  },
  computed: {
    buyRentMedianText() {
      if (!this.buyRentStats) return '-'
      const wan = this.buyRentStats.median / 10000
      const sign = wan >= 0 ? '+' : ''
      return sign + wan.toFixed(1) + ' 万'
    }
  },
  async mounted() {
    await Promise.all([this.loadStats(), this.loadBuyRentStats()])
  },
  methods: {
    async loadStats() {
      try {
        const response = await getRentRatioStats()
        if (response.success) {
          this.rentRatioMin = response.data.min
          this.rentRatioMax = response.data.max
          this.rentRatioAvg = response.data.average.toFixed(2)
          this.estateCount = response.data.count
        }
      } catch (error) {
        console.error('加载统计数据失败:', error)
      }
    },
    async loadBuyRentStats() {
      try {
        const response = await getBuyRentStats()
        if (response.success) {
          this.buyRentStats = response.data
        }
      } catch (error) {
        console.error('加载买租对比统计数据失败:', error)
      }
    },
    handleEstateSelect(estate) {
      // 通知地图组件定位到选中的小区
      if (this.$refs.mapView) {
        this.$refs.mapView.flyToEstate(estate)
      }
    },
    handleDataLoaded(data) {
      // 地图数据加载完成后的回调
      console.log('地图数据加载完成')
    }
  }
}
</script>

<style scoped>
.app-container {
  display: flex;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: 350px;
  background: #f5f5f5;
  padding: 20px;
  overflow-y: auto;
  box-shadow: 2px 0 8px rgba(0,0,0,0.1);
  z-index: 1000;
}

.header {
  margin-bottom: 20px;
}

.header h1 {
  font-size: 22px;
  color: #333;
  margin: 0 0 5px 0;
}

.subtitle {
  font-size: 12px;
  color: #666;
  margin: 0;
}

/* 指标切换开关 */
.view-switch {
  display: flex;
  background: #e0e0e0;
  border-radius: 6px;
  padding: 3px;
  margin-bottom: 15px;
}

.switch-btn {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  border-radius: 4px;
  font-size: 13px;
  color: #555;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn:hover {
  color: #333;
}

.switch-btn.active {
  background: white;
  color: #333;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.15);
}

.map-area {
  flex: 1;
  position: relative;
}

.stats-panel {
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  margin-top: 15px;
}

.stats-panel h3 {
  margin: 0 0 12px 0;
  font-size: 16px;
  color: #333;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  color: #666;
  font-size: 14px;
}

.stat-value {
  color: #4CAF50;
  font-weight: 600;
  font-size: 14px;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .app-container {
    flex-direction: column;
  }
  
  .sidebar {
    width: 100%;
    height: auto;
    max-height: 40vh;
    padding: 15px;
  }
  
  .map-area {
    height: 60vh;
  }
}
</style>
