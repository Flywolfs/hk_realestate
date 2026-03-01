/**
 * 色彩映射工具 - 小程序版本
 * 根据租售比值生成对应的颜色(绿色到红色渐变)
 */

/**
 * 将HSL颜色转换为十六进制
 * @param {number} h - 色相 (0-360)
 * @param {number} s - 饱和度 (0-100)
 * @param {number} l - 亮度 (0-100)
 * @returns {string} 十六进制颜色值
 */
function hslToHex(h, s, l) {
  l /= 100
  const a = s * Math.min(l, 1 - l) / 100
  const f = n => {
    const k = (n + h / 30) % 12
    const color = l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1)
    return Math.round(255 * color).toString(16).padStart(2, '0')
  }
  return `#${f(0)}${f(8)}${f(4)}`
}

/**
 * 根据租售比值返回对应的颜色
 * 新规则：以4%为基准值，7%为红色上限
 * - 租售比 < 4%: 绿色(120°)渐变到黄色(60°)
 * - 租售比 ≥ 4%: 黄色(60°)渐变到红色(0°)，7%及以上为纯红
 * @param {number|null} ratio - 租售比值
 * @param {number} min - 最小租售比(用于参考)
 * @param {number} max - 最大租售比(用于参考)
 * @returns {string} 颜色值(十六进制)
 */
function getRentRatioColor(ratio, min, max) {
  // 无租售比数据时显示灰色
  if (ratio === null || ratio === undefined) {
    return '#999999'
  }
  
  const PIVOT = 4  // 基准值4%(黄色)
  const RED_THRESHOLD = 7  // 红色阈值7%
  let hue
  
  if (ratio < PIVOT) {
    // 租售比 < 4%: 从绿色(120°)渐变到黄色(60°)
    const normalized = Math.min(ratio / PIVOT, 1)
    hue = 120 - (normalized * 60)  // 120° -> 60°
  } else {
    // 租售比 ≥ 4%: 从黄色(60°)渐变到红色(0°)
    // 4%为黄色，7%及以上为红色
    const normalized = Math.min((ratio - PIVOT) / (RED_THRESHOLD - PIVOT), 1)
    hue = 60 - (normalized * 60)  // 60° -> 0°
  }
  
  const saturation = 80
  const lightness = 50
  
  return hslToHex(hue, saturation, lightness)
}

/**
 * 获取渐变色彩数组(用于图例显示)
 * 基于新的4%基准值、7%红色上限规则生成渐变色
 * @param {number} steps - 渐变步数
 * @returns {Array} 颜色数组
 */
function getGradientColors(steps = 10) {
  const colors = []
  // 生成从0%到7%的渐变
  for (let i = 0; i < steps; i++) {
    const ratio = (i / (steps - 1)) * 7  // 0% -> 7%
    // 使用相同的颜色映射逻辑
    let hue
    if (ratio < 4) {
      const normalized = ratio / 4
      hue = 120 - (normalized * 60)
    } else {
      const normalized = Math.min((ratio - 4) / 3, 1)  // (4%, 7%] -> [0, 1]
      hue = 60 - (normalized * 60)
    }
    colors.push(hslToHex(hue, 80, 50))
  }
  return colors
}

module.exports = {
  getRentRatioColor,
  getGradientColors
}
