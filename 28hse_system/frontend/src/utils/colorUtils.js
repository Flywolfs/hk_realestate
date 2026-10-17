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
// 买租对比：10年资产差颜色映射（离散档位，按数据范围动态分档）
// 规则：以 0 为中心，负向按 |负向端点|、正向按正向端点各自等分为 5 档；
//       端点由调用方传入（默认取 P5/P95 分位截断，弱化极端值影响），
//       超出端点的取最深色；未提供端点时回退为每档 10 万（±50 万）
// ============================================================

export const BUY_RENT_STEP = 100000        // 回退档位跨度：每档 10 万
export const BUY_RENT_LEVELS_PER_SIDE = 5  // 正负各 5 档（共 11 档色带）

/**
 * 计算正负两侧每档对应的金额跨度
 * @param {number|null} min - 负向端点（负数，如 P5 分位数）
 * @param {number|null} max - 正向端点（正数，如 P95 分位数）
 * @returns {{negSpan: number, posSpan: number}} 负向/正向每档跨度（正数）
 */
export function getBuyRentSpans(min, max) {
  const fallback = BUY_RENT_STEP * BUY_RENT_LEVELS_PER_SIDE
  return {
    negSpan: (typeof min === 'number' && min < 0)
      ? Math.abs(min) / BUY_RENT_LEVELS_PER_SIDE
      : fallback,
    posSpan: (typeof max === 'number' && max > 0)
      ? max / BUY_RENT_LEVELS_PER_SIDE
      : fallback
  }
}

/**
 * 将买比租资金差换算为颜色档位（-5 ~ +5）
 * @param {number|null} score - 买比租的资金差（HKD，正=赚，负=亏）
 * @param {number|null} min - 负向端点（决定负向每档跨度）
 * @param {number|null} max - 正向端点（决定正向每档跨度）
 * @returns {number|null} 档位，无数据返回 null
 */
export function getBuyRentLevel(score, min = null, max = null) {
  if (score === null || score === undefined || isNaN(score)) {
    return null
  }
  const { negSpan, posSpan } = getBuyRentSpans(min, max)
  const span = score < 0 ? negSpan : posSpan
  // 对称就近取档
  const level = Math.sign(score) * Math.floor(Math.abs(score) / span + 0.5)
  return Math.max(-BUY_RENT_LEVELS_PER_SIDE, Math.min(BUY_RENT_LEVELS_PER_SIDE, level))
}

/**
 * 档位 → 颜色（0=黄，越负越绿/越亏，越正越红/越赚）
 * @param {number} level - 档位(-5 ~ +5)
 * @returns {string} 十六进制颜色
 */
function buyRentLevelToColor(level) {
  const hue = level < 0
    ? 60 + (-level / BUY_RENT_LEVELS_PER_SIDE) * 60   // 黄(60°) → 绿(120°)
    : 60 - (level / BUY_RENT_LEVELS_PER_SIDE) * 60    // 黄(60°) → 红(0°)
  return hslToHex(hue, 80, 50)
}

/**
 * 根据买比租资金差返回对应的颜色
 * @param {number|null} score - 资金差（HKD，正=赚/买划算，负=亏/租划算）
 * @param {number|null} min - 负向端点（决定负向每档跨度）
 * @param {number|null} max - 正向端点（决定正向每档跨度）
 * @returns {string} 颜色值(十六进制)
 */
export function getBuyRentColor(score, min = null, max = null) {
  const level = getBuyRentLevel(score, min, max)
  if (level === null) {
    return '#999999'
  }
  return buyRentLevelToColor(level)
}

/**
 * 获取买租对比渐变色彩数组（用于图例显示，离散档位色块）
 * @returns {Array} 颜色数组，从负向最深绿(最亏) 到 正向最深红(最赚)，共 11 档
 */
export function getBuyRentGradientColors() {
  const colors = []
  for (let level = -BUY_RENT_LEVELS_PER_SIDE; level <= BUY_RENT_LEVELS_PER_SIDE; level++) {
    colors.push(buyRentLevelToColor(level))
  }
  return colors
}
