/**
 * API封装
 * 提供与Flask后端交互的接口
 */
import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  response => response.data,
  error => {
    console.error('API请求错误:', error)
    return Promise.reject(error)
  }
)

/**
 * 获取所有小区列表（分页循环加载全量数据）
 * 自动分页请求并合并，返回格式与原接口完全兼容
 * @returns {Promise} 小区列表数据
 */
export async function getAllEstates() {
  const LIMIT = 2000
  let allData = []
  let page = 1
  let totalPages = 1

  while (page <= totalPages) {
    const res = await api.get('/estates', { params: { page, limit: LIMIT } })
    if (!res.success) throw new Error(res.error || '分页请求失败')
    allData = allData.concat(res.data)
    totalPages = res.total_pages
    page++
  }

  return { success: true, count: allData.length, data: allData }
}

/**
 * 获取特定小区详情
 * @param {string} estateId - 小区ID
 * @returns {Promise} 小区详情数据
 */
export async function getEstateDetail(estateId) {
  return api.get(`/estates/${estateId}`)
}

/**
 * 获取租售比统计信息
 * @returns {Promise} 租售比统计数据
 */
export async function getRentRatioStats() {
  return api.get('/rent-ratios')
}

/**
 * 搜索小区
 * @param {string} keyword - 搜索关键词
 * @returns {Promise} 搜索结果
 */
export async function searchEstates(keyword) {
  return api.get('/search', {
    params: { keyword }
  })
}

/**
 * 获取小学校网列表
 * @returns {Promise} 校网列表
 */
export async function getPrimarySchools() {
  return api.get('/primary-schools')
}

export default api
