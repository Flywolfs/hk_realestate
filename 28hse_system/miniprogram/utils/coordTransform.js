/**
 * 坐标系转换工具
 * WGS-84（GPS坐标）转 GCJ-02（火星坐标/腑讯地图）
 *
 * 关于香港地区的坐标系说明：
 * 微信小程序的地图组件（腑讯地图）无论在大陆还是香港，
 * 均需要 GCJ-02 坐标才能与地图瓦片对齐。
 * 后端数据为 WGS-84，必须转换后才能准确显示。
 */

const PI = Math.PI
const A = 6378245.0          // 长半轴
 const EE = 0.00669342162296594323  // 偏心率平方

/**
 * WGS-84 转 GCJ-02
 * @param {number} lng - WGS-84 经度
 * @param {number} lat - WGS-84 纬度
 * @returns {{ longitude: number, latitude: number }}
 */
function wgs84ToGcj02(lng, lat) {
  let dlat = transformLat(lng - 105.0, lat - 35.0)
  let dlng = transformLng(lng - 105.0, lat - 35.0)
  const radlat = (lat / 180.0) * PI
  let magic = Math.sin(radlat)
  magic = 1 - EE * magic * magic
  const sqrtmagic = Math.sqrt(magic)
  dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
  dlng = (dlng * 180.0) / (A / sqrtmagic * Math.cos(radlat) * PI)
  return {
    longitude: lng + dlng,
    latitude:  lat + dlat
  }
}

function transformLat(lng, lat) {
  let ret = -100.0 + 2.0 * lng + 3.0 * lat + 0.2 * lat * lat +
            0.1 * lng * lat + 0.2 * Math.sqrt(Math.abs(lng))
  ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(lat * PI) + 40.0 * Math.sin(lat / 3.0 * PI)) * 2.0 / 3.0
  ret += (160.0 * Math.sin(lat / 12.0 * PI) + 320.0 * Math.sin(lat * PI / 30.0)) * 2.0 / 3.0
  return ret
}

function transformLng(lng, lat) {
  let ret = 300.0 + lng + 2.0 * lat + 0.1 * lng * lng +
            0.1 * lng * lat + 0.1 * Math.sqrt(Math.abs(lng))
  ret += (20.0 * Math.sin(6.0 * lng * PI) + 20.0 * Math.sin(2.0 * lng * PI)) * 2.0 / 3.0
  ret += (20.0 * Math.sin(lng * PI) + 40.0 * Math.sin(lng / 3.0 * PI)) * 2.0 / 3.0
  ret += (150.0 * Math.sin(lng / 12.0 * PI) + 300.0 * Math.sin(lng / 30.0 * PI)) * 2.0 / 3.0
  return ret
}

/**
 * 批量将小区坐标从 WGS-84 转换为 GCJ-02
 * @param {Array} estates
 * @returns {Array}
 */
function batchTransformEstates(estates) {
  return estates.map(estate => {
    if (!estate.coordinates) return estate
    const { latitude, longitude } = estate.coordinates
    if (!latitude || !longitude) return estate
    const converted = wgs84ToGcj02(longitude, latitude)
    return {
      ...estate,
      coordinates: {
        latitude:  converted.latitude,
        longitude: converted.longitude
      }
    }
  })
}

module.exports = {
  wgs84ToGcj02,
  batchTransformEstates
}
