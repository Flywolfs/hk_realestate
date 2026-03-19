/**
 * API接口封装 - 小程序版本
 * 提供与Flask后端交互的接口
 * 
 * 注意：此文件现在作为统一的 API 入口，根据 app.js 的配置自动选择：
 * - 云调用模式 (useCloudMode = true): 使用 api.cloud.js
 * - HTTP 域名模式 (useCloudMode = false): 使用 api.http.js
 */

// 获取 app 实例以读取全局配置
const app = getApp()

// 根据全局配置决定使用哪个 API 模块
function getApiModule() {
  // 如果 app 还未初始化，默认使用 HTTP 模式
  if (!app) {
    console.warn('[API] app 未初始化，使用默认 HTTP 模式')
    return require('./api.http.js')
  }
  
  // 根据 useCloudMode 配置选择
  const useCloud = app.globalData && app.globalData.useCloudMode
  console.log(`[API] 当前模式: ${useCloud ? '云调用' : 'HTTP'}`)
  
  if (useCloud) {
    return require('./api.cloud.js')
  } else {
    return require('./api.http.js')
  }
}

// 获取实际的 API 模块
const apiModule = getApiModule()

// 导出 API 模块的所有方法
module.exports = apiModule
