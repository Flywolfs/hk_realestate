// app.js - 小程序主入口文件
App({
  globalData: {
    // 全局数据,用于页面间传递信息
    locateEstate: null,  // 从详情页返回时定位到的小区信息
    apiBaseUrl: 'http://localhost:5000/api',  // API基础URL,开发时使用,上线前需替换为HTTPS域名
    userInfo: null
  },

  onLaunch(options) {
    // 小程序启动时执行
    console.log('小程序启动', options)
    
    // 检查小程序版本更新
    this.checkUpdate()
    
    // 获取系统信息
    this.getSystemInfo()
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
  }
})
