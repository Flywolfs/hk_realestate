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
      
      <div class="filter-section">
        <h4>房屋类型</h4>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.showGongwu" @change="applyFilters" />
          <span>显示公屋</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.showJuwu" @change="applyFilters" />
          <span>显示居屋</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.showPrivate" @change="applyFilters" />
          <span>显示私人屋苑</span>
        </label>
      </div>
      
      <div class="filter-section">
        <h4>建成年份</h4>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.after2010" @change="applyFilters" />
          <span>2010年后</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.year2000to2010" @change="applyFilters" />
          <span>2000-2010年</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.year1990to2000" @change="applyFilters" />
          <span>1990-2000年</span>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="filters.before1990" @change="applyFilters" />
          <span>1990年前</span>
        </label>
      </div>
      
      <div class="filter-section" v-if="primarySchools.length > 0">
        <h4>小学校网 <span class="small-text">(共{{ primarySchools.length }}个)</span></h4>
        <div class="school-list">
          <label v-for="school in primarySchools" :key="school.school" class="checkbox-label">
            <input type="checkbox" v-model="filters.selectedSchools" :value="school.school" @change="applyFilters" />
            <span>校网 {{ school.school }} ({{ school.count }})</span>
          </label>
        </div>
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
import { getAllEstates, getEstateDetail, getRentRatioStats, getPrimarySchools } from '../utils/api.js'
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
      primarySchools: [],  // 小学校网列表
      filters: {
        below3: false,
        range3to3_5: false,
        range3_5to4: false,
        range4to5: false,
        above5: false,
        showGongwu: false,
        showJuwu: false,
        showPrivate: false,
        after2010: false,
        year2000to2010: false,
        year1990to2000: false,
        before1990: false,
        selectedSchools: []  // 选中的校网
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
        const [estatesResponse, statsResponse, schoolsResponse] = await Promise.all([
          getAllEstates(),
          getRentRatioStats(),
          getPrimarySchools()
        ])
        
        if (!estatesResponse.success || !statsResponse.success) {
          throw new Error('数据加载失败')
        }
        
        this.rentRatioStats = statsResponse.data
        this.allEstates = estatesResponse.data
        
        // 加载校网数据
        if (schoolsResponse.success) {
          this.primarySchools = schoolsResponse.data
        }
        
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
        color: '#333333',  // 边框颜色改为深灰色
        weight: 1.5,       // 边框宽度稍微减小
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
        if (!this.showGrayMarkers) return false
      }
      
      // === 租售比区间筛选 ===
      const anyRatioFilterSelected = this.filters.below3 || this.filters.range3to3_5 || 
                                      this.filters.range3_5to4 || this.filters.range4to5 || 
                                      this.filters.above5
      
      if (anyRatioFilterSelected && ratio !== null && ratio !== undefined) {
        let inRatioRange = false
        if (this.filters.below3 && ratio < 3) inRatioRange = true
        if (this.filters.range3to3_5 && ratio >= 3 && ratio < 3.5) inRatioRange = true
        if (this.filters.range3_5to4 && ratio >= 3.5 && ratio < 4) inRatioRange = true
        if (this.filters.range4to5 && ratio >= 4 && ratio < 5) inRatioRange = true
        if (this.filters.above5 && ratio >= 5) inRatioRange = true
        
        if (!inRatioRange) return false
      }
      
      // === 房屋类型筛选 ===
      const anyTypeFilterSelected = this.filters.showGongwu || this.filters.showJuwu || this.filters.showPrivate
      
      if (anyTypeFilterSelected) {
        const housingType = estate.housing_type
        let inTypeRange = false
        
        if (this.filters.showGongwu && housingType === 'gongwu') inTypeRange = true
        if (this.filters.showJuwu && housingType === 'juwu') inTypeRange = true
        if (this.filters.showPrivate && !housingType) inTypeRange = true  // 没有类型标记的为私人屋苑
        
        if (!inTypeRange) return false
      }
      
      // === 建成年份筛选 ===
      const anyYearFilterSelected = this.filters.after2010 || this.filters.year2000to2010 || 
                                     this.filters.year1990to2000 || this.filters.before1990
      
      if (anyYearFilterSelected) {
        const year = estate.establish_year
        if (!year || typeof year !== 'number') return false
        
        let inYearRange = false
        if (this.filters.after2010 && year > 2010) inYearRange = true
        if (this.filters.year2000to2010 && year >= 2000 && year <= 2010) inYearRange = true
        if (this.filters.year1990to2000 && year >= 1990 && year < 2000) inYearRange = true
        if (this.filters.before1990 && year < 1990) inYearRange = true
        
        if (!inYearRange) return false
      }
      
      // === 小学校网筛选 ===
      if (this.filters.selectedSchools.length > 0) {
        const school = estate.primary_school
        if (!this.filters.selectedSchools.includes(school)) return false
      }
      
      return true
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
        above5: false,
        showGongwu: false,
        showJuwu: false,
        showPrivate: false,
        after2010: false,
        year2000to2010: false,
        year1990to2000: false,
        before1990: false,
        selectedSchools: []
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

.filter-section h4 .small-text {
  font-size: 11px;
  color: #999;
  font-weight: normal;
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

.school-list {
  max-height: 200px;
  overflow-y: auto;
  padding-right: 5px;
}

.school-list::-webkit-scrollbar {
  width: 6px;
}

.school-list::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.school-list::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 3px;
}

.school-list::-webkit-scrollbar-thumb:hover {
  background: #555;
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
