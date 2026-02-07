<template>
  <div class="map-container">
    <div ref="map" class="map"></div>
    
    <!-- 筛选控制面板 -->
    <div class="filter-panel">
      <div class="filter-section">
        <label class="checkbox-label">
          <input type="checkbox" v-model="showGrayMarkers" @change="applyFilters" />
          <span>显示无租售比数据的小区</span>
        </label>
      </div>
      
      <div class="filter-section">
        <h4>租售比区间筛选</h4>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.below3" @change="applyFilters" />
          <span>< 3%</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.range3to3_5" @change="applyFilters" />
          <span>3% - 3.5%</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.range3_5to4" @change="applyFilters" />
          <span>3.5% - 4%</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.range4to5" @change="applyFilters" />
          <span>4% - 5%</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.above5" @change="applyFilters" />
          <span>> 5%</span>
        </label>
      </div>
      
      <button class="reset-btn" @click="resetFilters">重置筛选</button>
    </div>
    
    <div v-if="loading" class="loading-overlay">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>
    <div v-if="error" class="error-message">
      {{ error }}
    </div>
  </div>
</template>

<script>
import L from 'leaflet'
import { getAllEstates, getEstateDetail, getRentRatioStats } from '../utils/api.js'
import { getRentRatioColor } from '../utils/colorUtils.js'

export default {
  name: 'MapView',
  data() {
    return {
      map: null,
      markers: {},
      allEstates: [],  // 存储所有小区数据
      loading: true,
      error: null,
      rentRatioStats: null,
      showGrayMarkers: false,  // 是否显示灰色标记
      filters: {
        below3: false,
        range3to3_5: false,
        range3_5to4: false,
        range4to5: false,
        above5: false
      }
    }
  },
  mounted() {
    this.initMap()
    this.loadData()
  },
  methods: {
    initMap() {
      // 初始化地图,中心定位香港
      this.map = L.map(this.$refs.map).setView([22.3193, 114.1694], 11)
      
      // 添加OpenStreetMap图层
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
      }).addTo(this.map)
    },
    
    async loadData() {
      try {
        this.loading = true
        this.error = null
        
        // 并行获取数据
        const [estatesResponse, statsResponse] = await Promise.all([
          getAllEstates(),
          getRentRatioStats()
        ])
        
        if (!estatesResponse.success || !statsResponse.success) {
          throw new Error('数据加载失败')
        }
        
        this.rentRatioStats = statsResponse.data
        this.allEstates = estatesResponse.data
        
        // 为每个小区创建标记
        this.allEstates.forEach(estate => {
          this.addMarker(estate)
        })
        
        // 默认不显示灰色标记
        this.applyFilters()
        
        this.loading = false
      } catch (err) {
        console.error('加载数据失败:', err)
        this.error = '数据加载失败,请刷新页面重试'
        this.loading = false
      }
    },
    
    addMarker(estate) {
      const { latitude, longitude } = estate.coordinates
      const color = getRentRatioColor(
        estate.rent_ratio,
        this.rentRatioStats.min,
        this.rentRatioStats.max
      )
      
      // 创建圆形标记，半径从8改为6
      const marker = L.circleMarker([latitude, longitude], {
        radius: 6,
        fillColor: color,
        color: '#fff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8
      }).addTo(this.map)
      
      // 给marker添加自定义属性，用于筛选
      marker.estateData = estate
      
      // 绑定点击事件
      marker.on('click', async () => {
        await this.showEstateDetail(estate.id, marker)
      })
      
      // 保存标记引用
      this.markers[estate.id] = marker
    },
    
    async showEstateDetail(estateId, marker) {
      try {
        const response = await getEstateDetail(estateId)
        if (!response.success) {
          throw new Error('获取详情失败')
        }
        
        const detail = response.data
        
        // 构建Popup内容
        const popupContent = `
          <div class="estate-popup">
            <h3>${detail.name}</h3>
            <div class="popup-section">
              <strong>小区ID:</strong> ${detail.id}
            </div>
            <div class="popup-section">
              <strong>地址:</strong> ${detail.address || '暂无'}
            </div>
            <div class="popup-section">
              <strong>建立时间:</strong> ${detail.establish_year || '暂无'}
            </div>
            <div class="popup-section">
              <strong>开发商:</strong> ${detail.developer || '暂无'}
            </div>
            ${detail.building_count ? `
              <div class="popup-section">
                <strong>座数:</strong> ${detail.building_count}
              </div>
            ` : ''}
            ${detail.rent_ratio ? `
              <div class="popup-section highlight">
                <strong>租售比:</strong> ${detail.rent_ratio.toFixed(2)}%
              </div>
            ` : '<div class="popup-section"><strong>租售比:</strong> 暂无数据</div>'}
          </div>
        `
        
        marker.bindPopup(popupContent, {
          maxWidth: 300,
          className: 'custom-popup'
        }).openPopup()
      } catch (err) {
        console.error('获取小区详情失败:', err)
        marker.bindPopup('<div class="error">加载详情失败</div>').openPopup()
      }
    },
    
    // 公开方法:定位到指定小区
    flyToEstate(estate) {
      if (!estate || !estate.coordinates) return
      
      const { latitude, longitude } = estate.coordinates
      this.map.flyTo([latitude, longitude], 15, {
        duration: 1
      })
      
      // 打开该小区的Popup
      const marker = this.markers[estate.id]
      if (marker) {
        setTimeout(() => {
          this.showEstateDetail(estate.id, marker)
        }, 1000)
      }
    },
    
    // 判断小区是否在筛选范围内
    isInFilterRange(estate) {
      const ratio = estate.rent_ratio
      
      // 如果没有租售比数据
      if (ratio === null || ratio === undefined) {
        return this.showGrayMarkers
      }
      
      // 如果所有筛选都未选中，显示所有
      const anyFilterSelected = Object.values(this.filters).some(v => v)
      if (!anyFilterSelected) {
        return true
      }
      
      // 检查是否在选中的区间内
      if (this.filters.below3 && ratio < 3) return true
      if (this.filters.range3to3_5 && ratio >= 3 && ratio < 3.5) return true
      if (this.filters.range3_5to4 && ratio >= 3.5 && ratio < 4) return true
      if (this.filters.range4to5 && ratio >= 4 && ratio < 5) return true
      if (this.filters.above5 && ratio >= 5) return true
      
      return false
    },
    
    // 应用筛选
    applyFilters() {
      Object.values(this.markers).forEach(marker => {
        const estate = marker.estateData
        if (this.isInFilterRange(estate)) {
          marker.addTo(this.map)
        } else {
          marker.remove()
        }
      })
    },
    
    // 重置筛选
    resetFilters() {
      this.showGrayMarkers = false
      this.filters = {
        below3: false,
        range3to3_5: false,
        range3_5to4: false,
        range4to5: false,
        above5: false
      }
      this.applyFilters()
    }
  }
}
</script>

<style scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
}

.map {
  width: 100%;
  height: 100%;
}

/* 筛选控制面板 */
.filter-panel {
  position: absolute;
  top: 10px;
  right: 10px;
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
  z-index: 1000;
  max-width: 250px;
  max-height: 90vh;
  overflow-y: auto;
}

.filter-section {
  margin-bottom: 15px;
}

.filter-section h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #333;
  font-weight: 600;
}

.checkbox-label {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #555;
}

.checkbox-label input[type="checkbox"] {
  margin-right: 8px;
  cursor: pointer;
  width: 16px;
  height: 16px;
}

.checkbox-label span {
  user-select: none;
}

.checkbox-label:hover {
  color: #4CAF50;
}

.reset-btn {
  width: 100%;
  padding: 8px 12px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.3s;
}

.reset-btn:hover {
  background: #45a049;
}

.reset-btn:active {
  transform: translateY(1px);
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #4CAF50;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-overlay p {
  margin-top: 15px;
  color: #666;
  font-size: 16px;
}

.error-message {
  position: absolute;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  background: #f44336;
  color: white;
  padding: 12px 24px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  z-index: 1001;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .filter-panel {
    top: auto;
    bottom: 10px;
    right: 10px;
    left: 10px;
    max-width: none;
    max-height: 40vh;
  }
}
</style>

<style>
/* 全局样式用于Popup */
.custom-popup .leaflet-popup-content {
  margin: 0;
  width: auto !important;
}

.estate-popup {
  padding: 10px;
  min-width: 250px;
}

.estate-popup h3 {
  margin: 0 0 12px 0;
  color: #333;
  font-size: 18px;
  border-bottom: 2px solid #4CAF50;
  padding-bottom: 8px;
}

.popup-section {
  margin-bottom: 8px;
  font-size: 14px;
  line-height: 1.5;
}

.popup-section strong {
  color: #666;
}

.popup-section.highlight {
  background: #e8f5e9;
  padding: 8px;
  border-radius: 4px;
  margin-top: 10px;
}

.popup-section.highlight strong {
  color: #2e7d32;
}
</style>
