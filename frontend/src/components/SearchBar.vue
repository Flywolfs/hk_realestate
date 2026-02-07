<template>
  <div class="search-bar">
    <h3>搜索小区</h3>
    <div class="search-input-wrapper">
      <input 
        v-model="keyword" 
        type="text" 
        placeholder="输入小区名称..."
        @input="onSearch"
        class="search-input"
      />
      <div v-if="keyword && results.length > 0" class="search-results">
        <div 
          v-for="estate in results" 
          :key="estate.id"
          class="search-result-item"
          @click="selectEstate(estate)"
        >
          <div class="estate-name">{{ estate.name }}</div>
          <div class="estate-address">{{ estate.address }}</div>
          <div v-if="estate.rent_ratio" class="estate-ratio">
            租售比: {{ estate.rent_ratio.toFixed(2) }}%
          </div>
        </div>
      </div>
      <div v-if="keyword && results.length === 0 && !loading" class="no-results">
        未找到匹配的小区
      </div>
    </div>
  </div>
</template>

<script>
import { searchEstates } from '../utils/api.js'

export default {
  name: 'SearchBar',
  data() {
    return {
      keyword: '',
      results: [],
      loading: false,
      searchTimeout: null
    }
  },
  methods: {
    onSearch() {
      // 清除之前的定时器
      if (this.searchTimeout) {
        clearTimeout(this.searchTimeout)
      }
      
      // 如果关键词为空,清空结果
      if (!this.keyword.trim()) {
        this.results = []
        return
      }
      
      // 延迟搜索(防抖)
      this.searchTimeout = setTimeout(async () => {
        this.loading = true
        try {
          const response = await searchEstates(this.keyword)
          if (response.success) {
            this.results = response.data.slice(0, 10) // 最多显示10条
          }
        } catch (error) {
          console.error('搜索失败:', error)
        } finally {
          this.loading = false
        }
      }, 300)
    },
    selectEstate(estate) {
      // 发送事件给父组件,让地图定位到该小区
      this.$emit('select-estate', estate)
      // 清空搜索
      this.keyword = ''
      this.results = []
    }
  }
}
</script>

<style scoped>
.search-bar {
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  margin-bottom: 15px;
}

.search-bar h3 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #333;
}

.search-input-wrapper {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.3s;
}

.search-input:focus {
  border-color: #4CAF50;
}

.search-results {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ddd;
  border-top: none;
  border-radius: 0 0 4px 4px;
  max-height: 300px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.search-result-item {
  padding: 10px 12px;
  cursor: pointer;
  border-bottom: 1px solid #f0f0f0;
  transition: background-color 0.2s;
}

.search-result-item:hover {
  background-color: #f5f5f5;
}

.search-result-item:last-child {
  border-bottom: none;
}

.estate-name {
  font-weight: 500;
  color: #333;
  margin-bottom: 4px;
}

.estate-address {
  font-size: 12px;
  color: #666;
  margin-bottom: 2px;
}

.estate-ratio {
  font-size: 12px;
  color: #4CAF50;
  font-weight: 500;
}

.no-results {
  padding: 10px 12px;
  color: #999;
  font-size: 14px;
  text-align: center;
  background: white;
  border: 1px solid #ddd;
  border-top: none;
  border-radius: 0 0 4px 4px;
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
}
</style>
