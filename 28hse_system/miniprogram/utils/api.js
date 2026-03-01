/**
 * API接口封装 - 小程序版本
 * 提供与Flask后端交互的接口
 */

// 获取API基础URL
const app = getApp()
const BASE_URL = 'http://localhost:5000/api'  // 开发环境,上线前需替换为HTTPS域名

/**
 * 封装wx.request
 * @param {string} url - 请求路径
 * @param {string} method - 请求方法
 * @param {object} data - 请求数据
 * @returns {Promise} Promise对象
 */
function request(url, method = 'GET', data = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${BASE_URL}${url}`,
      method: method,
      data: data,
      header: {
        'Content-Type': 'application/json'
      },
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else {
          const error = new Error(`请求失败: ${res.statusCode}`)
          error.statusCode = res.statusCode
          reject(error)
        }
      },
      fail(err) {
        console.error('API请求失败:', url, err)
        reject(err)
      }
    })
  })
}

/**
 * 获取所有小区列表
 * @returns {Promise} 小区列表数据
 */
function getAllEstates() {
  return request('/estates')
}

/**
 * 获取特定小区详情
 * @param {string} estateId - 小区ID
 * @returns {Promise} 小区详情数据
 */
function getEstateDetail(estateId) {
  return request(`/estates/${estateId}`)
}

/**
 * 获取租售比统计信息
 * @returns {Promise} 租售比统计数据
 */
function getRentRatioStats() {
  return request('/rent-ratios')
}

/**
 * 搜索小区
 * @param {string} keyword - 搜索关键词
 * @returns {Promise} 搜索结果
 */
function searchEstates(keyword) {
  return request(`/search?keyword=${encodeURIComponent(keyword)}`)
}

/**
 * 获取小学校网列表
 * @returns {Promise} 校网列表
 */
function getPrimarySchools() {
  return request('/primary-schools')
}

module.exports = {
  getAllEstates,
  getEstateDetail,
  getRentRatioStats,
  searchEstates,
  getPrimarySchools
}
