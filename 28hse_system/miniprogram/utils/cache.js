/**
 * 缓存管理工具 - 小程序版本
 * 使用微信小程序Storage API进行数据缓存
 */

const CACHE_KEY_PREFIX = 'estate_cache_'
const CACHE_EXPIRE_TIME = 3600000  // 1小时(毫秒)

/**
 * 设置缓存
 * @param {string} key - 缓存键名
 * @param {*} data - 缓存数据
 */
function setCache(key, data) {
  try {
    const cacheData = {
      data: data,
      timestamp: Date.now()
    }
    wx.setStorageSync(CACHE_KEY_PREFIX + key, cacheData)
    console.log(`缓存已设置: ${key}`)
  } catch (error) {
    console.error('设置缓存失败:', error)
  }
}

/**
 * 获取缓存
 * @param {string} key - 缓存键名
 * @returns {*} 缓存数据,不存在或已过期返回null
 */
function getCache(key) {
  try {
    const cacheData = wx.getStorageSync(CACHE_KEY_PREFIX + key)
    if (cacheData) {
      const now = Date.now()
      // 检查是否过期
      if (now - cacheData.timestamp < CACHE_EXPIRE_TIME) {
        console.log(`从缓存读取: ${key}`)
        return cacheData.data
      } else {
        // 缓存已过期,删除它
        clearCache(key)
        console.log(`缓存已过期: ${key}`)
      }
    }
  } catch (error) {
    console.error('读取缓存失败:', error)
  }
  return null
}

/**
 * 清除指定缓存
 * @param {string} key - 缓存键名
 */
function clearCache(key) {
  try {
    wx.removeStorageSync(CACHE_KEY_PREFIX + key)
    console.log(`缓存已清除: ${key}`)
  } catch (error) {
    console.error('清除缓存失败:', error)
  }
}

/**
 * 清除所有缓存
 */
function clearAllCache() {
  try {
    const info = wx.getStorageInfoSync()
    info.keys.forEach(key => {
      if (key.startsWith(CACHE_KEY_PREFIX)) {
        wx.removeStorageSync(key)
      }
    })
    console.log('所有缓存已清除')
  } catch (error) {
    console.error('清除所有缓存失败:', error)
  }
}

/**
 * 获取缓存信息
 * @returns {object} 缓存统计信息
 */
function getCacheInfo() {
  try {
    const info = wx.getStorageInfoSync()
    const cacheKeys = info.keys.filter(key => key.startsWith(CACHE_KEY_PREFIX))
    return {
      totalKeys: cacheKeys.length,
      currentSize: info.currentSize,
      limitSize: info.limitSize,
      keys: cacheKeys
    }
  } catch (error) {
    console.error('获取缓存信息失败:', error)
    return null
  }
}

module.exports = {
  setCache,
  getCache,
  clearCache,
  clearAllCache,
  getCacheInfo
}
