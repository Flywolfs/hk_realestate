/**
 * Markdown解析工具
 * 将markdown文本转换为微信小程序rich-text支持的HTML格式
 */

/**
 * 解析markdown为HTML
 * @param {string} markdown - markdown文本
 * @returns {string} HTML字符串
 */
function parseMarkdown(markdown) {
  if (!markdown) return ''
  
  let html = markdown
  
  // 转义HTML特殊字符
  html = escapeHtml(html)
  
  // 解析代码块 (```code```)
  html = html.replace(/```([\s\S]*?)```/g, '<view class="pre"><text class="code">$1</text></view>')
  
  // 解析行内代码 (`code`)
  html = html.replace(/`([^`]+)`/g, '<text class="code">$1</text>')
  
  // 解析标题
  html = html.replace(/^### (.*$)/gim, '<view class="h3">$1</view>')
  html = html.replace(/^## (.*$)/gim, '<view class="h2">$1</view>')
  html = html.replace(/^# (.*$)/gim, '<view class="h1">$1</view>')
  
  // 解析粗体 (**text**)
  html = html.replace(/\*\*(.*?)\*\*/g, '<text class="strong">$1</text>')
  
  // 解析斜体 (*text*)
  html = html.replace(/\*(.*?)\*/g, '<text class="em">$1</text>')
  
  // 解析删除线 (~~text~~)
  html = html.replace(/~~(.*?)~~/g, '<text style="text-decoration: line-through;">$1</text>')
  
  // 解析链接 [text](url)
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<text class="a" data-url="$2">$1</text>')
  
  // 解析无序列表
  html = html.replace(/^(\s*)[-*+] (.*$)/gim, (match, indent, content) => {
    const level = Math.floor(indent.length / 2)
    return `<view class="li" style="padding-left: ${level * 40}rpx;">• ${content}</view>`
  })
  
  // 解析有序列表
  let orderIndex = 0
  html = html.replace(/^(\s*)\d+\. (.*$)/gim, (match, indent, content) => {
    const level = Math.floor(indent.length / 2)
    orderIndex++
    return `<view class="li" style="padding-left: ${level * 40}rpx;">${orderIndex}. ${content}</view>`
  })
  
  // 解析引用 (> text)
  html = html.replace(/^> (.*$)/gim, '<view style="border-left: 6rpx solid #4CAF50; padding-left: 20rpx; color: #666; margin: 16rpx 0;">$1</view>')
  
  // 解析水平线
  html = html.replace(/^---$/gim, '<view style="border-top: 2rpx solid #e0e0e0; margin: 30rpx 0;"></view>')
  
  // 解析换行（保留段落结构）
  const paragraphs = html.split('\n\n')
  html = paragraphs.map(p => {
    p = p.trim()
    if (!p) return ''
    // 如果已经是块级元素，不再包裹
    if (p.startsWith('<view') || p.startsWith('<text')) {
      return p
    }
    // 将单个换行转为<br/>
    p = p.replace(/\n/g, '<text>\n</text>')
    return `<view class="p">${p}</view>`
  }).join('')
  
  return html
}

/**
 * 转义HTML特殊字符
 * @param {string} text - 原始文本
 * @returns {string} 转义后的文本
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  }
  return text.replace(/[&<>"']/g, (m) => map[m])
}

/**
 * 从文本中提取屋苑名称
 * @param {string} text - 文本内容
 * @param {string[]} estateNames - 屋苑名称列表
 * @returns {string[]} 匹配到的屋苑名称
 */
function extractEstateNames(text, estateNames) {
  if (!text || !estateNames || estateNames.length === 0) {
    return []
  }
  
  const matched = []
  const lowerText = text.toLowerCase()
  
  estateNames.forEach(name => {
    if (!name) return
    
    // 检查是否包含屋苑名称
    const lowerName = name.toLowerCase()
    
    // 使用单词边界匹配，避免部分匹配
    // 例如"太古城"不应该匹配"太古城中心"
    const regex = new RegExp(`(^|[^\\w])${escapeRegExp(name)}([^\\w]|$)`, 'i')
    
    if (regex.test(text) && !matched.includes(name)) {
      matched.push(name)
    }
  })
  
  // 按名称长度降序排序，优先替换长的名称
  return matched.sort((a, b) => b.length - a.length)
}

/**
 * 转义正则特殊字符
 * @param {string} string - 原始字符串
 * @returns {string} 转义后的字符串
 */
function escapeRegExp(string) {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * 简单的markdown文本提取（用于预览）
 * @param {string} markdown - markdown文本
 * @param {number} maxLength - 最大长度
 * @returns {string} 纯文本预览
 */
function extractPlainText(markdown, maxLength = 100) {
  if (!markdown) return ''
  
  // 移除markdown标记
  let text = markdown
    .replace(/```[\s\S]*?```/g, '') // 代码块
    .replace(/`([^`]+)`/g, '$1') // 行内代码
    .replace(/\*\*(.*?)\*\*/g, '$1') // 粗体
    .replace(/\*(.*?)\*/g, '$1') // 斜体
    .replace(/~~(.*?)~~/g, '$1') // 删除线
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1') // 链接
    .replace(/^#+ /gim, '') // 标题
    .replace(/^[-*+] /gim, '') // 列表
    .replace(/^\d+\. /gim, '') // 有序列表
    .replace(/^> /gim, '') // 引用
    .replace(/\n/g, ' ') // 换行转空格
  
  // 截断
  if (text.length > maxLength) {
    text = text.substring(0, maxLength) + '...'
  }
  
  return text.trim()
}

module.exports = {
  parseMarkdown,
  extractEstateNames,
  extractPlainText,
  escapeHtml
}
