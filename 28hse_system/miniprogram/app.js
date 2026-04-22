// app.js - 小程序主入口文件
// 双模式支持：云调用模式 (callContainer) 和 HTTP 域名模式
// 通过修改 useCloudMode 配置切换模式

// ==================== 模式配置 ====================
// true:  云调用模式（推荐，无需配置服务器域名）
// false: HTTP 域名模式（备用，需要购买域名并配置服务器域名）
const USE_CLOUD_MODE = true

// 云调用配置（仅在 USE_CLOUD_MODE = true 时有效）
// 注意：这里的配置需要与 utils/api.cloud.js 中的 CLOUD_CONFIG 保持一致
// 双服务架构：数据服务(app) + Agent服务(agent)
const CLOUD_CONFIG = {
  env: 'prod-xxx',  // 微信云托管环境ID
  dataService: 'app',  // 数据服务名称（estates、rent-ratios、search等）
  agentService: 'agent' // Agent服务名称（chat、health等）
}

// 动态加载 API 模块
const api = USE_CLOUD_MODE 
  ? require('./utils/api.cloud.js')
  : require('./utils/api.http.js')

App({
  globalData: {
    // 全局数据,用于页面间传递信息
    locateEstate: null,  // 从详情页返回时定位到的小区信息
    apiBaseUrl: 'https://xxx',  // HTTP模式下的API基础URL
    userInfo: null,
    isLoggedIn: false,  // 登录状态
    useCloudMode: USE_CLOUD_MODE,  // 当前使用的模式
    cloudConfig: CLOUD_CONFIG      // 云调用配置
  },

  onLaunch(options) {
    // 小程序启动时执行
    console.log('小程序启动', options)
    console.log(`当前模式: ${USE_CLOUD_MODE ? '云调用模式' : 'HTTP域名模式'}`)
    
    // 检查基础库版本（云调用需要 2.23.0+）
    const systemInfo = wx.getSystemInfoSync()
    const sdkVersion = systemInfo.SDKVersion
    console.log(`基础库版本: ${sdkVersion}`)
    
    if (USE_CLOUD_MODE) {
      // 解析版本号进行比较
      const versionParts = sdkVersion.split('.').map(Number)
      const minVersion = [2, 23, 0]
      const isVersionValid = versionParts[0] > minVersion[0] || 
        (versionParts[0] === minVersion[0] && versionParts[1] > minVersion[1]) ||
        (versionParts[0] === minVersion[0] && versionParts[1] === minVersion[1] && versionParts[2] >= minVersion[2])
      
      if (!isVersionValid) {
        wx.showModal({
          title: '版本过低',
          content: `当前基础库版本 ${sdkVersion} 过低，请升级微信到最新版本`,
          showCancel: false
        })
        return
      }
    }
    
    // 检查小程序版本更新
    this.checkUpdate()
    
    // 获取系统信息
    this.getSystemInfo()
    
    // 云调用模式下初始化云环境
    if (USE_CLOUD_MODE && api.initCloud) {
      // 设置云调用配置
      if (api.setCloudConfig) {
        api.setCloudConfig(CLOUD_CONFIG)
      }
      api.initCloud().then(() => {
        console.log('云调用初始化完成')
        // 云调用模式下无需检查登录状态，后端自动获取用户身份
        this.globalData.isLoggedIn = true
      }).catch(err => {
        console.error('云调用初始化失败:', err)
        wx.showToast({
          title: '云服务初始化失败',
          icon: 'none'
        })
      })
    } else {
      // HTTP 模式下检查登录状态
      this.checkLoginStatus()
    }
  },

  onShow(options) {
    // 小程序显示时执行
    console.log('小程序显示', options)
  },

  onHide() {
    // 小程序隐藏时执行
    console.log('小程序隐藏')
  },

  checkUpdate() {
    // 检查小程序更新
    if (wx.canIUse('getUpdateManager')) {
      const updateManager = wx.getUpdateManager()
      
      updateManager.onCheckForUpdate((res) => {
        if (res.hasUpdate) {
          console.log('发现新版本')
        }
      })

      updateManager.onUpdateReady(() => {
        wx.showModal({
          title: '更新提示',
          content: '新版本已经准备好,是否重启应用?',
          success: (res) => {
            if (res.confirm) {
              updateManager.applyUpdate()
            }
          }
        })
      })

      updateManager.onUpdateFailed(() => {
        wx.showModal({
          title: '更新失败',
          content: '新版本下载失败,请检查网络',
          showCancel: false
        })
      })
    }
  },

  getSystemInfo() {
    // 获取系统信息
    const systemInfo = wx.getSystemInfoSync()
    this.globalData.systemInfo = systemInfo
    console.log('系统信息:', systemInfo)
  },

  // 检查登录状态
  checkLoginStatus() {
    // 云调用模式下无需检查，后端自动获取用户身份
    if (this.globalData.useCloudMode) {
      this.globalData.isLoggedIn = true
      return Promise.resolve({ valid: true })
    }
    
    // HTTP 模式下检查 Token
    api.checkLoginStatus().then(res => {
      if (res.valid) {
        this.globalData.isLoggedIn = true
        this.globalData.userInfo = res.userInfo
        console.log('用户已登录:', res.userInfo)
      } else {
        this.globalData.isLoggedIn = false
        console.log('用户未登录')
      }
    })
  },

  // 执行登录
  doLogin(userInfo = {}) {
    // 云调用模式下无需登录，直接返回成功
    if (this.globalData.useCloudMode) {
      this.globalData.isLoggedIn = true
      this.globalData.userInfo = userInfo
      return Promise.resolve({
        success: true,
        userInfo: userInfo,
        message: '云调用模式无需登录'
      })
    }
    
    // HTTP 模式下执行微信登录
    return new Promise((resolve, reject) => {
      api.wechatLogin(userInfo).then(res => {
        if (res.success) {
          this.globalData.isLoggedIn = true
          this.globalData.userInfo = res.userInfo
          resolve(res)
        } else {
          reject(new Error('登录失败'))
        }
      }).catch(reject)
    })
  },

  // 退出登录
  doLogout() {
    // HTTP 模式下清除 Token
    if (!this.globalData.useCloudMode) {
      api.logout()
    }
    this.globalData.isLoggedIn = false
    this.globalData.userInfo = null
  },

  // 切换 API 模式（用于动态切换，需谨慎使用）
  switchApiMode(useCloud) {
    if (useCloud === this.globalData.useCloudMode) {
      return Promise.resolve({ success: true, message: '当前已是该模式' })
    }
    
    // 注意：实际切换需要重新加载页面才能生效
    // 这里仅更新配置，建议通过修改 USE_CLOUD_MODE 后重启小程序
    return Promise.resolve({
      success: false,
      message: '请修改 app.js 中的 USE_CLOUD_MODE 配置后重新编译小程序'
    })
  }
})
