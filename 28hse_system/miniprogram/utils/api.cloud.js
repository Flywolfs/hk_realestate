/**
 * API接口封装 - 云调用版本 (callContainer)
 * 使用微信云托管 callContainer 实现免鉴权请求
 * 后端自动获取用户 openid、unionid 等信息
 */

// 云托管配置
const CLOUD_CONFIG = {
  env: 'prod-xxx', // 微信云托管环境ID，请替换为实际环境ID
  service: 'yyy' // 微信云托管服务名称，请替换为实际服务名
}

// 云调用实例
let cloudInstance = null

/**
 * 初始化云调用
 * 在 app.js onLaunch 中调用
 */
function initCloud() {
  if (cloudInstance) return Promise.resolve(cloudInstance)
  
  return new Promise((resolve, reject) => {
    try {
      // 初始化云开发环境
      wx.cloud.init()
      
      // 创建云调用实例
      cloudInstance = wx.cloud
      console.log('云调用初始化成功')
      resolve(cloudInstance)
    } catch (err) {
      console.error('云调用初始化失败:', err)
      reject(err)
    }
  })
}

/**
 * 封装 callContainer 请求
 * 自动携带用户身份信息（openid、unionid 等）
 * @param {string} path - 请求路径（不含域名）
 * @param {string} method - 请求方法
 * @param {object} data - 请求数据
 * @param {boolean} requireAuth - 是否需要登录（云调用模式下此参数忽略，始终携带身份）
 * @returns {Promise} Promise对象
 */
function request(path, method = 'GET', data = {}, requireAuth = false) {
  return new Promise((resolve, reject) => {
    // 确保云调用已初始化
    if (!cloudInstance) {
      reject(new Error('云调用未初始化，请先调用 initCloud()'))
      return
    }

    const options = {
      config: {
        env: CLOUD_CONFIG.env
      },
      path: `/api${path}`, // 添加 /api 前缀
      method: method,
      header: {
        'X-WX-SERVICE': CLOUD_CONFIG.service,
        'Content-Type': 'application/json'
      },
      data: data
    }

    cloudInstance.callContainer(options)
      .then(res => {
        if (res.statusCode === 200) {
          resolve(res.data)
        } else {
          const error = new Error(`请求失败: ${res.statusCode}`)
          error.statusCode = res.statusCode
          error.data = res.data
          reject(error)
        }
      })
      .catch(err => {
        console.error('云调用请求失败:', path, err)
        reject(err)
      })
  })
}

/**
 * 微信登录（云调用模式）
 * 云调用模式下无需真正的登录流程，后端自动从 header 获取 openid
 * 此方法保留用于兼容性，直接返回成功状态
 * @param {Object} userInfo - 可选的用户信息
 * @returns {Promise} 登录结果
 */
function wechatLogin(userInfo = {}) {
  return Promise.resolve({
    success: true,
    userInfo: userInfo,
    message: '云调用模式无需登录，用户身份自动获取'
  })
}

/**
 * 检查登录状态（云调用模式）
 * 云调用模式下始终返回已登录状态
 * @returns {Promise} 验证结果
 */
function checkLoginStatus() {
  // 云调用模式下，每次请求自动携带用户身份
  // 无需检查本地 token，直接返回有效状态
  return Promise.resolve({ 
    valid: true, 
    userInfo: null,
    message: '云调用模式自动获取用户身份'
  })
}

/**
 * 退出登录（云调用模式）
 * 云调用模式下无实际作用，保留接口用于兼容性
 */
function logout() {
  // 云调用模式下无 token 需要清除
  console.log('云调用模式无需退出登录')
}

/**
 * 获取存储的Token（云调用模式）
 * 始终返回 null，云调用模式下无需 token
 * @returns {null}
 */
function getToken() {
  return null
}

/**
 * 获取所有小区列表（分页循环加载全量数据）
 * 自动分页请求，合并后返回全部数据
 * @param {function} [onProgress] - 可选，进度回调 onProgress(loaded, total)
 * @returns {Promise} 小区列表数据
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
 * 更新云托管配置
 * @param {Object} config - 配置对象
 * @param {string} config.env - 云托管环境ID
 * @param {string} config.service - 云托管服务名称
 */
function setCloudConfig(config) {
  if (config.env) CLOUD_CONFIG.env = config.env
  if (config.service) CLOUD_CONFIG.service = config.service
  console.log('云托管配置已更新:', CLOUD_CONFIG)
}

module.exports = {
  // 云调用初始化
  initCloud,
  setCloudConfig,
  // 数据API
  getAllEstates,
  getEstateDetail,
  getRentRatioStats,
  searchEstates,
  getPrimarySchools,
  // 登录相关（云调用模式下为兼容保留）
  wechatLogin,
  checkLoginStatus,
  logout,
  getToken,
  // 带认证的请求（云调用模式下与普通请求相同）
  requestWithAuth: (url, method = 'GET', data = {}) => request(url, method, data, true)
}
