/**
 * 色彩映射工具
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
export function getRentRatioColor(ratio, min, max) {
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
export function getGradientColors(steps = 10) {
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

// ============================================================
// 买租对比：10年资产差颜色映射（离散档位）
// 规则：每档 10 万港元；绿(亏) → 黄(0附近) → 红(赚)；
//       超过 ±50 万统一取最深色；无数据显示灰色
// ============================================================

export const BUY_RENT_STEP = 100000        // 每个颜色级别对应 10 万
const BUY_RENT_MAX_LEVEL = 5               // ±5 档封顶（即 ±50 万）

/**
 * 将买比租资金差换算为颜色档位（-5 ~ +5，±5万内归 0 档）
 * @param {number|null} score - 买比租的资金差（HKD，正=赚，负=亏）
 * @returns {number|null} 档位，无数据返回 null
 */
export function getBuyRentLevel(score) {
  if (score === null || score === undefined || isNaN(score)) {
    return null
  }
  // 对称就近取档
  const level = Math.sign(score) * Math.floor(Math.abs(score) / BUY_RENT_STEP + 0.5)
  return Math.max(-BUY_RENT_MAX_LEVEL, Math.min(BUY_RENT_MAX_LEVEL, level))
}

/**
 * 档位 → 颜色（0=黄，越负越绿/越亏，越正越红/越赚）
 * @param {number} level - 档位(-5 ~ +5)
 * @returns {string} 十六进制颜色
 */
function buyRentLevelToColor(level) {
  const hue = level < 0
    ? 60 + (-level / BUY_RENT_MAX_LEVEL) * 60   // 黄(60°) → 绿(120°)
    : 60 - (level / BUY_RENT_MAX_LEVEL) * 60    // 黄(60°) → 红(0°)
  return hslToHex(hue, 80, 50)
}

/**
 * 根据买比租资金差返回对应的颜色
 * @param {number|null} score - 资金差（HKD，正=赚/买划算，负=亏/租划算）
 * @returns {string} 颜色值(十六进制)
 */
export function getBuyRentColor(score) {
  const level = getBuyRentLevel(score)
  if (level === null) {
    return '#999999'
  }
  return buyRentLevelToColor(level)
}

/**
 * 获取买租对比渐变色彩数组（用于图例显示，离散档位色块）
 * @returns {Array} 颜色数组，从 -50万 (最绿) 到 +50万 (最红)，共 11 档
 */
export function getBuyRentGradientColors() {
  const colors = []
  for (let level = -BUY_RENT_MAX_LEVEL; level <= BUY_RENT_MAX_LEVEL; level++) {
    colors.push(buyRentLevelToColor(level))
  }
  return colors
}
