// pages/chat/chat.js - 港房通AI对话页面
const { parseMarkdown, extractEstateNames } = require('../../utils/markdownParser.js')
const api = require('../../utils/api.js')

// 获取所有屋苑名称用于匹配（从全局数据或本地存储）
let estateNameCache = null

Page({
  data: {
    messages: [],
    inputValue: '',
    isLoading: false,
    statusText: '',
    scrollToMessage: '',
    currentTaskId: null,
    pollingTimer: null,
    streamingMessageId: null // 当前流式传输的消息ID
  },

  onLoad(options) {
    // 加载屋苑名称缓存
    this.loadEstateNames()
    
    // 如果有传入的初始消息
    if (options.message) {
      this.setData({ inputValue: options.message })
      this.sendMessage()
    }
  },

  onUnload() {
    // 清理轮询定时器
    this.clearPolling()
  },

  // 加载屋苑名称列表
  async loadEstateNames() {
    if (estateNameCache) {
      return estateNameCache
    }
    
    try {
      // 尝试从本地存储获取
      const cached = wx.getStorageSync('estate_names_cache')
      if (cached && cached.length > 0) {
        estateNameCache = cached
        return cached
      }
      
      // 从API获取
      const res = await api.getAllEstates()
      if (res.success && res.data) {
        const names = res.data.map(e => e.name).filter(n => n)
        estateNameCache = names
        wx.setStorageSync('estate_names_cache', names)
        return names
      }
    } catch (error) {
      console.error('加载屋苑名称失败:', error)
    }
    return []
  },

  // 输入变化
  onInputChange(e) {
    this.setData({
      inputValue: e.detail.value
    })
  },

  // 发送消息
  async sendMessage() {
    const { inputValue, isLoading } = this.data
    const message = inputValue.trim()
    
    if (!message || isLoading) return

    // 添加用户消息
    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message
    }

    this.setData({
      messages: [...this.data.messages, userMessage],
      inputValue: '',
      isLoading: true,
      scrollToMessage: `msg-${userMessage.id}`
    })

    try {
      // 发送消息到Agent服务
      await this.sendToAgent(message)
    } catch (error) {
      console.error('发送消息失败:', error)
      this.addErrorMessage('发送失败，请稍后重试')
    }
  },

  // 发送消息到Agent服务
  async sendToAgent(message) {
    try {
      // 1. 发送消息获取task_id
      const res = await api.sendAgentMessage(message)
      
      if (!res.success) {
        throw new Error(res.error || '请求失败')
      }

      const { task_id } = res
      this.setData({ currentTaskId: task_id })

      // 2. 开始轮询结果
      this.startPolling(task_id)
    } catch (error) {
      console.error('Agent请求失败:', error)
      this.addErrorMessage('服务暂时不可用，请稍后重试')
    }
  },

  // 开始轮询任务结果（流式更新）
  startPolling(taskId) {
    this.clearPolling()
    
    let retryCount = 0
    const maxRetries = 120 // 最多轮询120次（约2分钟）
    
    const poll = async () => {
      try {
        const res = await api.getAgentResult(taskId)
        
        if (!res.success) {
          throw new Error(res.error || '获取结果失败')
        }

        const { status, partial_reply, tools_used, status_text } = res

        // 更新状态文本
        if (status_text) {
          this.setData({ statusText: status_text })
        }

        if (status === 'done') {
          // 任务完成，最终更新AI回复
          this.updateOrAddAIResponse(partial_reply, tools_used, true)
          this.clearPolling()
        } else if (status === 'error') {
          // 任务出错
          this.addErrorMessage('生成回复时出错，请重试')
          this.clearPolling()
        } else {
          // 仍在处理中，实时更新流式内容
          if (partial_reply && partial_reply.trim()) {
            this.updateOrAddAIResponse(partial_reply, tools_used, false)
          }
          
          // 继续轮询
          retryCount++
          if (retryCount < maxRetries) {
            const timer = setTimeout(poll, 1000)
            this.setData({ pollingTimer: timer })
          } else {
            this.addErrorMessage('请求超时，请稍后重试')
            this.clearPolling()
          }
        }
      } catch (error) {
        console.error('轮询失败:', error)
        retryCount++
        if (retryCount < maxRetries) {
          const timer = setTimeout(poll, 1000)
          this.setData({ pollingTimer: timer })
        } else {
          this.addErrorMessage('请求超时，请稍后重试')
          this.clearPolling()
        }
      }
    }

    // 立即开始第一次轮询
    poll()
  },

  // 更新或添加AI回复（流式显示）
  updateOrAddAIResponse(content, toolsUsed = [], isFinal = false) {
    const { messages, streamingMessageId } = this.data
    const renderedContent = this.renderMarkdown(content)
    
    if (streamingMessageId) {
      // 更新已有流式消息
      const msgIndex = messages.findIndex(m => m.id === streamingMessageId)
      if (msgIndex !== -1) {
        const updatedMessages = [...messages]
        updatedMessages[msgIndex] = {
          ...updatedMessages[msgIndex],
          content: content,
          renderedContent: renderedContent,
          toolsUsed: toolsUsed,
          isFinal: isFinal
        }
        this.setData({
          messages: updatedMessages,
          scrollToMessage: `msg-${streamingMessageId}`
        })
        
        if (isFinal) {
          this.setData({ streamingMessageId: null })
        }
        return
      }
    }
    
    // 创建新的流式消息
    const aiMessage = {
      id: Date.now().toString(),
      role: 'assistant',
      content: content,
      renderedContent: renderedContent,
      toolsUsed: toolsUsed,
      isFinal: isFinal
    }

    this.setData({
      messages: [...messages, aiMessage],
      streamingMessageId: isFinal ? null : aiMessage.id,
      scrollToMessage: `msg-${aiMessage.id}`
    })
  },

  // 清理轮询
  clearPolling() {
    const { pollingTimer } = this.data
    if (pollingTimer) {
      clearTimeout(pollingTimer)
    }
    this.setData({ 
      pollingTimer: null,
      isLoading: false,
      statusText: ''
    })
  },

  // 添加AI回复
  addAIResponse(content, toolsUsed = []) {
    // 解析markdown并提取屋苑名称
    const renderedContent = this.renderMarkdown(content)
    
    const aiMessage = {
      id: Date.now().toString(),
      role: 'assistant',
      content: content,
      renderedContent: renderedContent,
      toolsUsed: toolsUsed
    }

    this.setData({
      messages: [...this.data.messages, aiMessage],
      scrollToMessage: `msg-${aiMessage.id}`
    })
  },

  // 添加错误消息
  addErrorMessage(errorText) {
    const errorMessage = {
      id: Date.now().toString(),
      role: 'assistant',
      content: errorText,
      renderedContent: `<span style="color:#f44336;">${errorText}</span>`,
      isError: true
    }

    this.setData({
      messages: [...this.data.messages, errorMessage],
      isLoading: false,
      scrollToMessage: `msg-${errorMessage.id}`
    })
  },

  // 渲染markdown并处理屋苑名称
  renderMarkdown(content) {
    // 1. 提取屋苑名称
    const estateNames = extractEstateNames(content, estateNameCache || [])
    
    // 2. 解析markdown
    let html = parseMarkdown(content)
    
    // 3. 将屋苑名称转换为可点击链接
    estateNames.forEach(name => {
      // 使用正则替换，但避免重复替换
      const regex = new RegExp(`(${this.escapeRegExp(name)})(?![^<]*>|[^<>]*</)`, 'g')
      html = html.replace(regex, `<span style="color:#4CAF50;text-decoration:underline;font-weight:500;">$1</span>`)
    })
    
    return html
  },

  // 转义正则特殊字符
  escapeRegExp(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  },

  // 处理rich-text点击事件（屋苑名称点击）
  onRichTextTap(e) {
    const { node } = e.detail
    if (node && node.attrs && node.attrs['data-name']) {
      const estateName = node.attrs['data-name']
      this.navigateToEstate(estateName)
    }
  },

  // 跳转到屋苑详情
  async navigateToEstate(estateName) {
    wx.showLoading({ title: '加载中...' })
    
    try {
      // 搜索屋苑获取ID
      const res = await api.searchEstates(estateName)
      
      if (res.success && res.data && res.data.length > 0) {
        // 找到最匹配的屋苑
        const estate = res.data.find(e => e.name === estateName) || res.data[0]
        
        wx.navigateTo({
          url: `/pages/estate-detail/estate-detail?id=${estate.id}`
        })
      } else {
        wx.showToast({
          title: '未找到该屋苑',
          icon: 'none'
        })
      }
    } catch (error) {
      console.error('跳转失败:', error)
      wx.showToast({
        title: '加载失败',
        icon: 'none'
      })
    } finally {
      wx.hideLoading()
    }
  },

  // 清除对话历史
  async clearHistory() {
    try {
      await api.clearAgentHistory()
      this.setData({ messages: [] })
      wx.showToast({ title: '已清除', icon: 'success' })
    } catch (error) {
      console.error('清除历史失败:', error)
    }
  },

  // 分享配置
  onShareAppMessage() {
    return {
      title: '港房通AI助手 - 智能房产咨询',
      path: '/pages/chat/chat'
    }
  }
})
