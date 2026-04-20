/**
 * API接口封装 - HTTP 域名方案（备用）
 * 提供与Flask后端交互的接口
 * 当云调用服务不可用时，可通过购买域名并配置服务器域名继续使用
 */

// 获取API基础URL
const app = getApp()
const BASE_URL = 'https://hkrealestate-230834-6-1409178104.sh.run.tcloudbase.com/api'  // 开发环境,上线前需替换为HTTPS域名

// Token存储键名
const TOKEN_KEY = 'auth_token'

/**
 * 获取存储的Token
 * @returns {string|null} Token字符串
 */
function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || null
}

/**
 * 设置Token
 * @param {string} token - Token字符串
 */
function setToken(token) {
  wx.setStorageSync(TOKEN_KEY, token)
}

/**
 * 清除Token
 */
function clearToken() {
  wx.removeStorageSync(TOKEN_KEY)
}

/**
 * 封装wx.request
 * @param {string} url - 请求路径
 * @param {string} method - 请求方法
 * @param {object} data - 请求数据
 * @param {boolean} requireAuth - 是否需要登录
 * @returns {Promise} Promise对象
 */
function request(url, method = 'GET', data = {}, requireAuth = false) {
  return new Promise((resolve, reject) => {
    const header = {
      'Content-Type': 'application/json'
    }
    
    // 如果需要认证，添加Token
    if (requireAuth) {
      const token = getToken()
      if (token) {
        header['Authorization'] = `Bearer ${token}`
      }
    }
    
    wx.request({
      url: `${BASE_URL}${url}`,
      method: method,
      data: data,
      header: header,
      success(res) {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else if (res.statusCode === 401) {
          // Token过期或无效，清除Token并提示登录
          clearToken()
          reject({ ...res.data, needLogin: true })
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
 * 微信登录
 * 获取code并发送到后端换取Token
 * @param {Object} userInfo - 可选的用户信息（通过button获取）
 * @returns {Promise} 登录结果
 */
function wechatLogin(userInfo = {}) {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (res) => {
        if (res.code) {
          console.log('获取到 code:', res.code.substring(0, 10) + '...')
          
          // 直接发送code和用户信息到后端
          // 用户信息可能为空（如果用户未授权）
          request('/auth/login', 'POST', {
            code: res.code,
            userInfo: userInfo
          }).then(loginRes => {
            if (loginRes.success && loginRes.data.token) {
              setToken(loginRes.data.token)
              resolve({
                success: true,
                userInfo: userInfo,
                token: loginRes.data.token
              })
            } else {
              reject(new Error(loginRes.error || '登录失败'))
            }
          }).catch(reject)
        } else {
          reject(new Error('获取code失败: ' + (res.errMsg || '未知错误')))
        }
      },
      fail: (err) => {
        console.error('wx.login 失败:', err)
        reject(err)
      }
    })
  })
}

/**
 * 检查登录状态
 * @returns {Promise} 验证结果
 */
function checkLoginStatus() {
  const token = getToken()
  if (!token) {
    return Promise.resolve({ valid: false })
  }
  
  return request('/auth/verify', 'GET', {})
    .then(res => {
      if (res.success && res.valid) {
        return { valid: true, userInfo: res.data }
      }
      clearToken()
      return { valid: false }
    })
    .catch(() => {
      clearToken()
      return { valid: false }
    })
}

/**
 * 退出登录
 */
function logout() {
  clearToken()
}

/**
 * 获取所有小区列表（分页循环加载全量数据）
 * 自动分页请求，合并后返回全部数据，与原 getAllEstates 接口完全兼容
 * @param {function} [onProgress] - 可选，进度回调 onProgress(loaded, total)
 * @returns {Promise} 小区列表数据（格式同 getAllEstates）
 */
function getAllEstates(onProgress) {
  const LIMIT = 2000
  let allData = []
  let total = null

  function fetchPage(page) {
    return request(`/estates?page=${page}&limit=${LIMIT}`).then(res => {
      if (!res.success) throw new Error(res.error || '分页请求失败')
      if (total === null) total = res.count
      allData = allData.concat(res.data)
      if (onProgress) onProgress(allData.length, total)
      // 若还有下一页，继续请求
      if (page < res.total_pages) {
        return fetchPage(page + 1)
      }
    })
  }

  return fetchPage(1).then(() => ({
    success: true,
    count: allData.length,
    data: allData
  }))
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

/**
 * Agent服务相关API
 */

/**
 * 发送消息到Agent
 * @param {string} message - 用户消息
 * @returns {Promise} 包含task_id的响应
 */
function sendAgentMessage(message) {
  return request('/agent/chat', 'POST', { message }, true)
}

/**
 * 获取Agent任务结果
 * @param {string} taskId - 任务ID
 * @returns {Promise} 任务结果
 */
function getAgentResult(taskId) {
  return request(`/agent/chat/result?task_id=${taskId}`, 'GET', {}, true)
}

/**
 * 清除Agent对话历史
 * @returns {Promise} 响应结果
 */
function clearAgentHistory() {
  return request('/agent/clear', 'POST', {}, true)
}

/**
 * 获取Agent服务健康状态
 * @returns {Promise} 健康状态
 */
function getAgentHealth() {
  return request('/agent/health', 'GET')
}

module.exports = {
  // 数据API
  getAllEstates,
  getEstateDetail,
  getRentRatioStats,
  searchEstates,
  getPrimarySchools,
  // 登录相关
  wechatLogin,
  checkLoginStatus,
  logout,
  getToken,
  // 带认证的请求（需要登录才能访问）
  requestWithAuth: (url, method = 'GET', data = {}) => request(url, method, data, true),
  // Agent服务API
  sendAgentMessage,
  getAgentResult,
  clearAgentHistory,
  getAgentHealth
}
