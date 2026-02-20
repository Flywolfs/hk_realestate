<template>
  <div class="app-container">
    <div class="sidebar">
      <div class="header">
        <h1>香港小区租售比地图</h1>
        <p class="subtitle">Hong Kong Rent-Sale Ratio Map</p>
      </div>
      
      <SearchBar @select-estate="handleEstateSelect" />
      
      <ColorLegend 
        :min-value="rentRatioMin" 
        :max-value="rentRatioMax" 
      />
      
      <div class="stats-panel">
        <h3>数据统计</h3>
        <div class="stat-item">
          <span class="stat-label">小区总数:</span>
          <span class="stat-value">{{ estateCount }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均租售比:</span>
          <span class="stat-value">{{ rentRatioAvg }}%</span>
        </div>
      </div>
    </div>
    
    <div class="map-area">
      <MapView ref="mapView" @data-loaded="handleDataLoaded" />
    </div>
  </div>
</template>

<script>
import MapView from './components/MapView.vue'
import SearchBar from './components/SearchBar.vue'
import ColorLegend from './components/ColorLegend.vue'
import { getRentRatioStats } from './utils/api.js'

export default {
  name: 'App',
  components: {
    MapView,
    SearchBar,
    ColorLegend
  },
  data() {
    return {
      rentRatioMin: 0,
      rentRatioMax: 10,
      rentRatioAvg: 0,
      estateCount: 0
    }
  },
  async mounted() {
    await this.loadStats()
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
