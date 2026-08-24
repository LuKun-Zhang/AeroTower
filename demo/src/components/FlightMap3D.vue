<template>
  <div ref="container" class="flight3d-container">
    <div class="flight3d-loading" v-if="!sceneReady">
      <div class="loading-spinner"></div>
      <span>{{ loadingText }}</span>
    </div>
  </div>
</template>

<script>
/**
 * FlightMap3D — Three.js 3D 航班模拟场景
 * ├── 中国地图绿色底座 + 地形高度位移
 * ├── 机场 3D 标记点（发光圆点 + 文字标签）
 * ├── 航线贝塞尔弧线（颜色区分状态）
 * ├── A320 飞机模型加载与沿航线动画
 * └── 交互：点击/悬停航线，相机聚焦
 */
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'
import * as echarts from 'echarts'
import '@/utils/china'

/* ==================== 地理常量（与 WeatherMap3D 一致） ==================== */
var CHINA = { minLng: 73, maxLng: 135, minLat: 18, maxLat: 54 }
var MAP_W = 60
var MAP_H = MAP_W * (CHINA.maxLat - CHINA.minLat) / (CHINA.maxLng - CHINA.minLng)
// 地图放大倍率：地形/机场/航线等地图元素整体放大 10 倍，飞机模型保持原尺寸，
// 视觉上飞机相对地图缩小；动画进度仍按航班规定时间驱动（飞行速度等效提升）
var MAP_SCALE = 10

function lngLatToWorld(lng, lat) {
  var wx = ((lng - CHINA.minLng) / (CHINA.maxLng - CHINA.minLng) - 0.5) * MAP_W
  var wz = (0.5 - (lat - CHINA.minLat) / (CHINA.maxLat - CHINA.minLat)) * MAP_H
  return { x: wx, z: wz }
}

/* ==================== 城市名 → 经纬度映射 ==================== */
var CITY_COORDS = {
  '北京': [116.4551, 40.2539], '上海': [121.4648, 31.2891],
  '广州': [113.5107, 23.2196], '深圳': [114.5435, 22.5439],
  '成都': [103.9526, 30.7617], '重庆': [107.7539, 30.1904],
  '昆明': [102.9199, 25.4663], '西安': [109.1162, 34.2004],
  '武汉': [114.3896, 30.6628], '南京': [118.8062, 31.9208],
  '杭州': [119.5313, 29.8773], '天津': [117.4219, 39.4189],
  '长沙': [113.0823, 28.2568], '郑州': [113.4668, 34.6234],
  '济南': [117.1582, 36.8701], '青岛': [120.4651, 36.3373],
  '大连': [122.2229, 39.4409], '沈阳': [123.1238, 42.1216],
  '哈尔滨': [127.9688, 45.368], '长春': [125.8154, 44.2584],
  '福州': [119.4543, 25.9222], '厦门': [118.1689, 24.6478],
  '海口': [110.3893, 19.8516], '三亚': [109.5186, 18.2582],
  '南宁': [108.479, 23.1152], '贵阳': [106.6992, 26.7682],
  '兰州': [103.5901, 36.3043], '西宁': [101.4038, 36.8207],
  '银川': [106.3586, 38.1775], '乌鲁木齐': [87.9236, 43.5883],
  '拉萨': [91.1865, 30.1465], '呼和浩特': [111.4124, 40.4901],
  '太原': [112.3352, 37.9413], '石家庄': [114.4995, 38.1006],
  '合肥': [117.29, 32.0581], '南昌': [116.0046, 28.6633],
  '苏州': [120.6519, 31.3989], '无锡': [120.3442, 31.5527],
  '宁波': [121.5967, 29.6466], '温州': [120.498, 27.8119],
  '珠海': [113.7305, 22.1155], '汕头': [117.1692, 23.3405],
  '湛江': [110.3655, 21.2772], '桂林': [110.2964, 25.2799],
  '丽江': [100.2336, 26.8625], '西昌': [102.2695, 27.9006],
  '芒市': [98.5886, 24.4538], '琼海': [110.4805, 19.2642],
  '康定': [101.9635, 30.0044], '稻城': [100.3044, 29.0431],
  '林芝': [94.3611, 29.6365], '阜阳': [115.8214, 32.8959],
  '浦东': [121.5440, 31.2211], '阿克苏': [80.2606, 41.1688],
  '喀什': [76.0003, 39.4737], '甘孜': [101.9625, 30.0493],
  '神农架': [110.6760, 31.7445], '九寨沟': [103.684, 32.857],
  '宜昌': [111.2930, 30.6976], '襄阳': [112.2501, 32.2292],
  '烟台': [120.7397, 37.5128], '威海': [121.9482, 37.1393],
  '徐州': [117.5208, 34.3268], '扬州': [119.4653, 32.8162],
  '洛阳': [112.4600, 34.6244], '包头': [110.3467, 41.4899],
  '鄂尔多斯': [108.9734, 39.2487], '延安': [109.1052, 36.4252],
  '汉中': [107.0302, 33.0738], '绵阳': [104.6862, 31.4734],
  '宜宾': [104.6481, 28.7576], '泸州': [105.4491, 28.8776],
  '大理': [100.2742, 25.6122], '丽江': [100.2336, 26.8625],
  '西双版纳': [100.8038, 22.0138], '敦煌': [94.6627, 40.1422],
  '格尔木': [94.9097, 36.4086], '日喀则': [88.9561, 29.2682],
}

function getCityCoord(cityName) {
  if (!cityName) return null
  if (CITY_COORDS[cityName]) return CITY_COORDS[cityName]
  var short = cityName.replace(/市|县|地区|自治州|州/g, '')
  if (CITY_COORDS[short]) return CITY_COORDS[short]
  for (var key in CITY_COORDS) {
    if (cityName.indexOf(key) !== -1 || key.indexOf(short) !== -1) return CITY_COORDS[key]
  }
  return null
}

/* ==================== GLSL: 地形地面 Shader ==================== */
var TERRAIN_VERT = [
  'uniform sampler2D uHeightTex;',
  'uniform float uElevationScale;',
  'varying vec2 vUv;',
  'varying float vElevation;',
  'void main(){',
  '  float h=dot(texture2D(uHeightTex,uv).rgb,vec3(0.299,0.587,0.114));',
  '  h=max(h,0.);',
  '  vec3 pos=position;',
  '  pos.z+=h*uElevationScale;',
  '  vElevation=h;',
  '  vUv=uv;',
  '  gl_Position=projectionMatrix*modelViewMatrix*vec4(pos,1.);',
  '}'
].join('\n')

var TERRAIN_FRAG = [
  'uniform sampler2D uChinaMap;',
  'uniform sampler2D uChinaMask;',
  'varying vec2 vUv;',
  'varying float vElevation;',
  'void main(){',
  '  vec3 elevCol = vec3(0.20, 0.55, 0.20);',
  '  vec4 mapC=texture2D(uChinaMap,vUv);',
  '  float mapDark=1.-mapC.r;',
  '  elevCol=mix(elevCol,elevCol*.7,mapDark*.45);',
  '  float mask=texture2D(uChinaMask,vUv).r;',
  '  if(mask<0.4)discard;',
  '  gl_FragColor=vec4(elevCol,1.);',
  '}'
].join('\n')

/* ==================== 航线颜色 ==================== */
var STATUS_COLORS = {
  flying: 0x409eff,
  landed: 0x4caf50,
  delayed: 0xff9800,
  cancelled: 0xf44336,
}

/* ==================== 机型模型映射（与座位视图共用同一批 GLB） ==================== */
var PLANE_MODEL_PATHS = {
  A319: '/models/a319.glb',
  A320: '/models/A320.glb',
  A321: '/models/a321.glb',
}
var PLANE_MODEL_TARGET_SIZE = 1.6

export default {
  name: 'FlightMap3D',
  props: {
    flights: { type: Array, default: function() { return [] } },
    currentTime: { type: [String, Number], default: '' },
    airportList: { type: Array, default: function() { return [] } },
  },
  data: function() {
    return {
      sceneReady: false,
      loadingText: '初始化场景...',
    }
  },
  watch: {
    flights: {
      deep: true,
      handler: function(newFlights) {
        if (this.sceneReady && newFlights && newFlights.length > 0) {
          this._updateFlights(newFlights)
        }
      },
    },
  },
  methods: {
    /* ==================== 中国地图纹理 ==================== */
    _createChinaTextures: function() {
      var M = 2048
      var self = this
      var toX = function(lng) { return (lng - CHINA.minLng) / (CHINA.maxLng - CHINA.minLng) * M }
      var toY = function(lat) { return (1 - (lat - CHINA.minLat) / (CHINA.maxLat - CHINA.minLat)) * M }

      var maskCanvas = document.createElement('canvas')
      maskCanvas.width = M; maskCanvas.height = M
      var mCtx = maskCanvas.getContext('2d')
      mCtx.fillStyle = '#000'; mCtx.fillRect(0, 0, M, M)

      var mapCanvas = document.createElement('canvas')
      mapCanvas.width = M; mapCanvas.height = M
      var mapCtx = mapCanvas.getContext('2d')
      mapCtx.fillStyle = '#e8ecf2'; mapCtx.fillRect(0, 0, M, M)

      var provinceColors = [
        '#f2f5f8','#eef2f6','#f0f3f7','#ecf0f5','#f3f6f9',
        '#edf1f6','#f1f4f8','#eef1f5','#f2f5f9','#ecf0f4',
        '#f0f3f6','#eef2f5','#f1f4f7','#edf1f4','#f2f4f8',
        '#ecf0f3','#f0f2f6','#eef1f4','#f1f3f7','#edf0f5',
      ]

      var colorIdx = 0

      try {
        var geo = echarts.getMap('china')
        if (geo && geo.geoJSON) {
          geo.geoJSON.features.forEach(function(feature) {
            var name = feature.properties ? feature.properties.name : ''
            var coords = feature.geometry ? feature.geometry.coordinates : null
            if (!coords || !name) return

            var color = provinceColors[colorIdx % provinceColors.length]
            colorIdx++

            var rings = []
            var flatten = function(c) {
              if (!c || !c.length) return
              if (typeof c[0][0] === 'number') { rings.push(c) }
              else { c.forEach(flatten) }
            }
            flatten(coords)

            var cx, cy
            var cp = feature.properties ? feature.properties.cp : null
            if (cp && Array.isArray(cp) && cp.length === 2) {
              cx = toX(cp[0]); cy = toY(cp[1])
            } else {
              var sumX = 0, sumY = 0, ptCnt = 0
              var mainRing = rings[0] || []
              mainRing.forEach(function(pt) { sumX += toX(pt[0]); sumY += toY(pt[1]); ptCnt++ })
              cx = ptCnt ? sumX / ptCnt : M / 2
              cy = ptCnt ? sumY / ptCnt : M / 2
            }

            mCtx.fillStyle = '#fff'
            rings.forEach(function(ring) {
              mCtx.beginPath()
              ring.forEach(function(pt, i) {
                var x = toX(pt[0]), y = toY(pt[1])
                i === 0 ? mCtx.moveTo(x, y) : mCtx.lineTo(x, y)
              })
              mCtx.closePath(); mCtx.fill()
            })

            mapCtx.fillStyle = color
            mapCtx.strokeStyle = '#4a5070'
            mapCtx.lineWidth = 2.4
            rings.forEach(function(ring) {
              mapCtx.beginPath()
              ring.forEach(function(pt, i) {
                var x = toX(pt[0]), y = toY(pt[1])
                i === 0 ? mapCtx.moveTo(x, y) : mapCtx.lineTo(x, y)
              })
              mapCtx.closePath()
              mapCtx.fill(); mapCtx.stroke()
            })
          })
        }
      } catch (_) {
        mCtx.fillStyle = '#fff'; mCtx.fillRect(0, 0, M, M)
        mapCtx.fillStyle = '#131a2a'; mapCtx.fillRect(0, 0, M, M)
      }

      this._chinaMaskTex = new THREE.CanvasTexture(maskCanvas)
      this._chinaMaskTex.minFilter = THREE.LinearFilter
      this._chinaMaskTex.magFilter = THREE.LinearFilter

      this._chinaMapTex = new THREE.CanvasTexture(mapCanvas)
      this._chinaMapTex.minFilter = THREE.LinearFilter
      this._chinaMapTex.magFilter = THREE.LinearFilter
    },

    /* ==================== 地形地面 ==================== */
    _createTerrainGround: function() {
      var self = this
      var heightCanvas = document.createElement('canvas')
      heightCanvas.width = 512; heightCanvas.height = 512
      var heightCtx = heightCanvas.getContext('2d')
      var heightTex = new THREE.CanvasTexture(heightCanvas)
      this._terrainTex = heightTex
      heightTex.minFilter = THREE.LinearMipmapLinearFilter
      heightTex.magFilter = THREE.LinearFilter

      var img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = function() {
        heightCtx.drawImage(img, 0, 0, 512, 512)
        var imageData = heightCtx.getImageData(0, 0, 512, 512)
        var d = imageData.data
        for (var i = 0; i < d.length; i += 4) {
          var r = d[i], g = d[i+1], bb = d[i+2]
          var h
          if (r > 235 && g > 235 && bb > 235 && Math.abs(r - g) < 8 && Math.abs(r - bb) < 8) {
            h = 245
          } else if (r > 200 && g > 200 && bb > 175 && r + g + bb > 650 && g <= r + 10) {
            h = 245
          } else if (r > 140 && r > g + 28 && g > bb + 35 && r + g + bb < 350) {
            h = 170
          } else if (r > 155 && r > g + 12 && bb < g - 8 && r > bb + 52) {
            h = 155
          } else if (g > r || (g + 5 > r && bb < g)) {
            h = 45
          } else {
            h = 10
          }
          d[i] = d[i+1] = d[i+2] = h
        }
        heightCtx.putImageData(imageData, 0, 0)
        heightTex.needsUpdate = true
      }
      try {
        img.src = require('@/assets/china_terrain.jpg')
      } catch (_) {}

      var gGeo = new THREE.PlaneGeometry(MAP_W, MAP_H, 300, 300)
      var gMat = new THREE.ShaderMaterial({
        vertexShader: TERRAIN_VERT,
        fragmentShader: TERRAIN_FRAG,
        uniforms: {
          uHeightTex: { value: heightTex },
          uChinaMap: { value: this._chinaMapTex },
          uChinaMask: { value: this._chinaMaskTex },
          uElevationScale: { value: 0.3 },
        },
        side: THREE.DoubleSide,
      })
      this._groundMesh = new THREE.Mesh(gGeo, gMat)
      this._groundMesh.rotation.x = -Math.PI / 2
      this._mapGroup.add(this._groundMesh)

      var borderGeo = new THREE.EdgesGeometry(gGeo)
      var borderLine = new THREE.LineSegments(borderGeo, new THREE.LineBasicMaterial({ color: 0x3a4060, transparent: true, opacity: 0.4 }))
      borderLine.rotation.x = -Math.PI / 2
      borderLine.position.y = 0.01
      this._mapGroup.add(borderLine)
    },

    /* ==================== 机场标记 ==================== */
    _createAirportMarker: function(cityName, lng, lat) {
      var pos = lngLatToWorld(lng, lat)
      var group = new THREE.Group()

      var ringGeo = new THREE.RingGeometry(0.3, 0.4, 32)
      var ringMat = new THREE.MeshBasicMaterial({
        color: 0x409eff, side: THREE.DoubleSide, transparent: true, opacity: 0.7,
      })
      var ring = new THREE.Mesh(ringGeo, ringMat)
      ring.rotation.x = -Math.PI / 2
      ring.position.y = 0.05
      group.add(ring)

      var sphereGeo = new THREE.SphereGeometry(0.2, 16, 16)
      var sphereMat = new THREE.MeshPhongMaterial({
        color: 0x409eff, emissive: 0x2060aa, emissiveIntensity: 0.6,
      })
      var sphere = new THREE.Mesh(sphereGeo, sphereMat)
      sphere.position.y = 0.25
      group.add(sphere)

      var outerRingGeo = new THREE.RingGeometry(0.45, 0.55, 32)
      var outerRingMat = new THREE.MeshBasicMaterial({
        color: 0x409eff, side: THREE.DoubleSide, transparent: true, opacity: 0.3,
      })
      var outerRing = new THREE.Mesh(outerRingGeo, outerRingMat)
      outerRing.rotation.x = -Math.PI / 2
      outerRing.position.y = 0.03
      group.add(outerRing)

      var labelCanvas = document.createElement('canvas')
      labelCanvas.width = 256; labelCanvas.height = 64
      var lctx = labelCanvas.getContext('2d')
      lctx.fillStyle = '#ffffff'
      lctx.font = 'bold 32px "Microsoft YaHei",sans-serif'
      lctx.textAlign = 'center'
      lctx.textBaseline = 'middle'
      lctx.shadowColor = 'rgba(0,0,0,0.7)'
      lctx.shadowBlur = 4
      lctx.fillText(cityName, 128, 32)

      var labelTex = new THREE.CanvasTexture(labelCanvas)
      labelTex.minFilter = THREE.LinearFilter
      var labelSpriteMat = new THREE.SpriteMaterial({
        map: labelTex, transparent: true, depthTest: false, depthWrite: false,
      })
      var labelSprite = new THREE.Sprite(labelSpriteMat)
      labelSprite.position.y = 0.9
      labelSprite.scale.set(3, 0.75, 1)
      group.add(labelSprite)

      group.position.set(pos.x, 0.02, pos.z)
      group.userData = { cityName: cityName, lng: lng, lat: lat }
      this._mapGroup.add(group)

      this._airportMarkers.push({ group: group, label: labelSprite, name: cityName, position: pos })
      return group
    },

    _createAllAirportMarkers: function() {
      var addedCities = {}
      var self = this
      Object.keys(CITY_COORDS).forEach(function(name) {
        if (addedCities[name]) return
        addedCities[name] = true
        var coord = CITY_COORDS[name]
        self._createAirportMarker(name, coord[0], coord[1])
      })
    },

    /* ==================== 航线弧（三阶段曲线：爬升→巡航→下降） ==================== */
    _buildCurve: function(flightData) {
      var depLng = flightData.depLng, depLat = flightData.depLat
      var arrLng = flightData.arrLng, arrLat = flightData.arrLat

      var startPos = lngLatToWorld(depLng, depLat)
      var endPos = lngLatToWorld(arrLng, arrLat)

      var dx = endPos.x - startPos.x
      var dz = endPos.z - startPos.z

      var groundY = 0.35          // 跑道/地面高度
      var cruiseAlt = Math.max(1.2, (flightData.altitude || 8000) / 900) * 0.4  // 巡航高度（世界坐标，降到原来40%）

      // 七控制点：起飞 → 爬升 → 巡航入口 → 巡航中点 → 巡航出口 → 下降 → 落地
      var cp = [
        new THREE.Vector3(startPos.x,                                   groundY,                startPos.z),
        new THREE.Vector3(startPos.x + dx * 0.06,  cruiseAlt * 0.35,  startPos.z + dz * 0.06),
        new THREE.Vector3(startPos.x + dx * 0.16,  cruiseAlt,           startPos.z + dz * 0.16),
        new THREE.Vector3(startPos.x + dx * 0.50,  cruiseAlt,           startPos.z + dz * 0.50),
        new THREE.Vector3(startPos.x + dx * 0.84,  cruiseAlt,           startPos.z + dz * 0.84),
        new THREE.Vector3(startPos.x + dx * 0.94,  cruiseAlt * 0.30,  startPos.z + dz * 0.94),
        new THREE.Vector3(endPos.x,                                   groundY,                endPos.z),
      ]

      var curve = new THREE.CatmullRomCurve3(cp, false, 'catmullrom', 0.5)
      flightData._phaseBreaks = { climbEnd: 0.16, cruiseEnd: 0.84 }  // 供仪表盘使用
      flightData._cruiseAlt = cruiseAlt * 900  // 还原为米
      flightData._depPos = { x: startPos.x, z: startPos.z }
      flightData._arrPos = { x: endPos.x, z: endPos.z }
      return curve
    },

    _createRouteArc: function(flightData) {
      var status = flightData.status
      var curve = this._buildCurve(flightData)

      var points = curve.getPoints(80)
      var geo = new THREE.BufferGeometry().setFromPoints(points)
      var color = STATUS_COLORS[status] || STATUS_COLORS.flying

      // 延误/取消航班优先显示：更高渲染优先级 + 更高不透明度，避免被正常航线遮挡
      var isAffected = status === 'delayed' || status === 'cancelled'
      var lineOpacity = isAffected ? 0.85 : 0.55
      var renderOrder = status === 'cancelled' ? 3 : (status === 'delayed' ? 2 : 1)
      var glowOpacity = isAffected ? 0.35 : 0.18

      var mat = new THREE.LineBasicMaterial({
        color: color, transparent: true, opacity: lineOpacity,
      })
      var line = new THREE.Line(geo, mat)
      line.userData = { flightData: flightData, curve: curve, isRoute: true }
      line.renderOrder = renderOrder
      line.material.depthTest = true
      this._mapGroup.add(line)

      var glowMat = new THREE.LineBasicMaterial({
        color: color, transparent: true, opacity: glowOpacity,
      })
      var glowGroup = new THREE.Group()

      var offsets = [[0.08, 0], [-0.08, 0], [0, 0.08], [0, -0.08]]
      offsets.forEach(function(off) {
        var ox = off[0], oz = off[1]
        var offPoints = points.map(function(p) { return new THREE.Vector3(p.x + ox, p.y, p.z + oz) })
        var offGeo = new THREE.BufferGeometry().setFromPoints(offPoints)
        var offLine = new THREE.Line(offGeo, glowMat.clone())
        offLine.renderOrder = 0
        glowGroup.add(offLine)
      })

      glowGroup.userData = { isGlow: true, parentLine: line }
      this._mapGroup.add(glowGroup)

      var entry = { line: line, glowGroup: glowGroup, curve: curve, flightData: flightData }
      this._routeLines.push(entry)
      return entry
    },

    /* ==================== 飞机模型加载（按机型 A319/A320/A321 对齐） ==================== */
    _loadPlaneModels: function() {
      var self = this
      self.loadingText = '加载飞机模型...'
      self._planeModels = {}
      return new Promise(function(resolve) {
        var done = false
        var safetyTimer = null
        var settle = function() {
          if (done) return
          done = true
          if (safetyTimer) clearTimeout(safetyTimer)
          if (!self._planeModels['A320']) {
            // 兜底：任何模型都未加载成功时使用占位几何体，避免无限转圈
            var ph = self._createPlaceholderPlane()
            self._planeModels['A320'] = ph
            self._planeModels['A319'] = ph
            self._planeModels['A321'] = ph
          }
          resolve(self._planeModels['A320'])
        }

        // 安全兜底：超过 30 秒仍未加载完成则用已加载模型/占位体继续
        safetyTimer = setTimeout(function() {
          console.warn('飞机模型加载超时，使用已加载模型继续')
          settle()
        }, 30000)

        var loadOne = function(acType, onDone) {
          var loader = new GLTFLoader()
          var dracoLoader = new DRACOLoader()
          dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
          loader.setDRACOLoader(dracoLoader)

          loader.load(
            PLANE_MODEL_PATHS[acType],
            function(gltf) {
              try {
                var model = self._normalizePlaneModel(gltf.scene)
                self._planeModels[acType] = model
                console.log(acType + ' 模型加载成功')
                onDone(model)
              } catch (err) {
                console.warn(acType + ' 模型归一化失败: ' + (err && err.message))
                onDone(null)
              }
            },
            undefined,
            function() {
              console.warn(acType + ' 模型加载失败，回退到 A320 模型')
              onDone(null)
            }
          )
        }

        // 先加载 A320 作基准模型，再依次加载 A319/A321，失败回退到 A320
        loadOne('A320', function(a320) {
          if (a320) {
            loadOne('A319', function() {
              if (!self._planeModels['A319']) self._planeModels['A319'] = a320
              loadOne('A321', function() {
                if (!self._planeModels['A321']) self._planeModels['A321'] = a320
                settle()
              })
            })
          } else {
            settle()
          }
        })
      })
    },

    /* 归一化 GLB 模型：机身摆正到 Z 轴、机头统一朝 +Z、居中、统一缩放 */
    _normalizePlaneModel: function(model) {
      // 居中
      var box = new THREE.Box3().setFromObject(model)
      var center = box.getCenter(new THREE.Vector3())
      model.position.set(-center.x, -center.y, -center.z)

      // 机身轴判别（机翼沿轴对称、机身沿轴不对称），与座位视图共用同一套标定：
      // 机身沿 X 轴则绕 Y 转 90° 摆正到 Z 轴（A319 机身已在 Z 轴，无需旋转）
      if (this.fuselageAlongX(model)) model.rotation.y = Math.PI / 2

      // 机头方向判别：若机头朝 -Z 则绕 Y 翻转 180°，统一为 +Z（动画前进方向）
      var boxZ = new THREE.Box3().setFromObject(model)
      var sizeZ = boxZ.getSize(new THREE.Vector3())
      if (!this.detectNose(model, sizeZ.z / 2)) model.rotation.y += Math.PI

      // 统一缩放：各机型到相同视觉尺寸
      var box2 = new THREE.Box3().setFromObject(model)
      var size = box2.getSize(new THREE.Vector3())
      var maxDim = Math.max(size.x, size.y, size.z)
      var scale = PLANE_MODEL_TARGET_SIZE / maxDim
      model.scale.setScalar(scale)

      // 缩放后再次居中（世界中心归零）
      var box3 = new THREE.Box3().setFromObject(model)
      var c3 = box3.getCenter(new THREE.Vector3())
      model.position.sub(c3)

      model.traverse(function(child) {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })
      return model
    },

    /* 机身轴判别：统计全部顶点在水平两轴两侧的分布，取不对称性更大的轴为机身轴 */
    fuselageAlongX: function(plane) {
      var v = new THREE.Vector3()
      var acc = {
        x: { neg: 0, pos: 0, cNeg: 0, cPos: 0 },
        z: { neg: 0, pos: 0, cNeg: 0, cPos: 0 },
      }
      var count = 0
      plane.updateMatrixWorld(true)
      plane.traverse(function(o) {
        if (!o.isMesh || !o.geometry) return
        var pos = o.geometry.attributes.position
        if (!pos) return
        var m = o.matrixWorld
        for (var i = 0; i < pos.count; i++) {
          v.set(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(m)
          count++
          if (v.x < 0) { acc.x.neg += v.x; acc.x.cNeg++ } else { acc.x.pos += v.x; acc.x.cPos++ }
          if (v.z < 0) { acc.z.neg += v.z; acc.z.cNeg++ } else { acc.z.pos += v.z; acc.z.cPos++ }
        }
      })
      if (count === 0) {
        var box = new THREE.Box3().setFromObject(plane)
        var size = box.getSize(new THREE.Vector3())
        return size.x >= size.z
      }
      var asym = function(a) {
        var negM = a.cNeg ? -a.neg / a.cNeg : 0
        var posM = a.cPos ? a.pos / a.cPos : 0
        return Math.abs(posM - negM) / Math.max(posM, negM, 1e-6)
      }
      return asym(acc.x) > asym(acc.z)
    },

    /* 机头方向判别：机身两端最外侧顶点平均半径更小（收敛锥形）的一端为机头 */
    detectNose: function(plane, halfLen) {
      plane.updateMatrixWorld(true)
      var v = new THREE.Vector3()
      var rPos = 0, rNeg = 0, cntPos = 0, cntNeg = 0
      plane.traverse(function(o) {
        if (!o.isMesh || !o.geometry) return
        var pos = o.geometry.attributes.position
        if (!pos) return
        var m = o.matrixWorld
        var limit = halfLen * 0.7
        for (var i = 0; i < pos.count; i++) {
          v.set(pos.getX(i), pos.getY(i), pos.getZ(i)).applyMatrix4(m)
          var r = Math.sqrt(v.x * v.x + v.y * v.y)
          if (v.z > limit) { rPos += r; cntPos++ }
          else if (v.z < -limit) { rNeg += r; cntNeg++ }
        }
      })
      if (cntPos === 0 || cntNeg === 0) return true
      return (rPos / cntPos) <= (rNeg / cntNeg)
    },

    _createPlaceholderPlane: function() {
      var group = new THREE.Group()
      var bodyGeo = new THREE.CylinderGeometry(0.052, 0.052, 0.8, 8)
      bodyGeo.rotateX(Math.PI / 2)
      var bodyMat = new THREE.MeshPhongMaterial({ color: 0xffffff })
      group.add(new THREE.Mesh(bodyGeo, bodyMat))
      var wingGeo = new THREE.BoxGeometry(0.33, 0.01, 0.08)
      group.add(new THREE.Mesh(wingGeo, bodyMat))
      var tailGeo = new THREE.BoxGeometry(0.033, 0.12, 0.067)
      var tail = new THREE.Mesh(tailGeo, new THREE.MeshPhongMaterial({ color: 0x2266cc }))
      tail.position.set(0.18, 0.05, 0)
      group.add(tail)
      return group
    },

    _createPlaneInstance: function(flightData, routeEntry) {
      if (!this._planeModels) return null

      // 按航班机型选择对应模型，未知机型回退 A320
      var acType = flightData.ac_type || 'A320'
      var source = this._planeModels[acType] || this._planeModels['A320']
      if (!source) return null

      var clone = source.clone(true)
      var group = new THREE.Group()
      group.add(clone)

      var startPoint = routeEntry.curve.getPoint(0)
      group.position.copy(startPoint).multiplyScalar(MAP_SCALE)

      this._scene.add(group)

      var instance = {
        group: group,
        curve: routeEntry.curve,
        progress: flightData.progress || 0,
        targetProgress: flightData.progress || 0,
        speed: 0.08 + Math.random() * 0.04,
        grounded: false,
        flightData: flightData,
      }
      this._planeInstances.push(instance)
      return instance
    },

    /* ==================== 更新航班数据 ==================== */
    _removeFlightEntry: function(entry) {
      // 航线弧（line / glowGroup）是 _mapGroup 的子节点，必须从 _mapGroup 移除，
      // 否则航班结束后弧形轮廓会残留在场景里。
      if (entry.line) {
        entry.line.geometry.dispose()
        entry.line.material.dispose()
        this._mapGroup.remove(entry.line)
      }
      if (entry.glowGroup) {
        entry.glowGroup.children.forEach(function(c) { c.geometry.dispose(); c.material.dispose() })
        this._mapGroup.remove(entry.glowGroup)
      }
    },

    _removePlaneInstance: function(inst) {
      this._scene.remove(inst.group)
      inst.group.traverse(function(c) { if (c.geometry) c.geometry.dispose(); if (c.material) c.material.dispose() })
    },

    _flightId: function(f) {
      // 用航班号作稳定 ID，无航班号时用起降机场拼接
      if (f.flight_no) return f.flight_no
      if (f.flightNo) return f.flightNo
      var dep = f.dep_airport || f.departure_airport || ''
      var arr = f.arr_airport || f.arrival_airport || ''
      if (dep && arr) return dep + '-' + arr
      return 'f_' + Math.random().toString(36).slice(2, 8)
    },

    /* 根据航班起降时间和当前模拟时钟计算 0-1 进度 */
    _calcTimeProgress: function(f) {
      // 优先用实际起降时间（延误后），否则回退计划时间
      var schedDep = f.actual_dep || f.scheduled_dep || f.scheduledDep
      var schedArr = f.actual_arr || f.scheduled_arr || f.scheduledArr
      if (!schedDep || !schedArr) return null
      var curStr = this.currentTime
      if (!curStr || curStr === '--') return null

      function toMs(arr) { return new Date(arr[0], arr[1]-1, arr[2], arr[3]||0, arr[4]||0).getTime() }
      var depMs = toMs(schedDep)
      var arrMs = toMs(schedArr)
      // 解析 "YYYY-MM-DD HH:MM" 或 ISO 格式
      var curMs = new Date(curStr.replace(' ', 'T')).getTime()
      if (isNaN(curMs)) return null
      var total = arrMs - depMs
      if (total <= 0) return null
      return Math.max(0, Math.min(1, (curMs - depMs) / total))
    },

    _updateFlights: function(flights) {
      if (!flights || !this._planeModels || !this._planeModels['A320']) return

      var self = this
      // 需要渲染航线的航班：空中 / 取消 / 延误（未起飞的延误停地面）
      var renderMap = {}  // id -> { f, isAirborne, isCancelled, grounded }
      flights.forEach(function(f) {
        var isAirborne = !!f.is_airborne
        var isCancelled = !!f.is_cancelled
        var grounded = !isAirborne && !!f.is_delayed
        if (!isAirborne && !isCancelled && !grounded) return
        renderMap[self._flightId(f)] = {
          f: f, isAirborne: isAirborne, isCancelled: isCancelled, grounded: grounded,
        }
      })

      // 航线轮廓只在航班「空中」阶段显示：起飞前 / 取消 / 延误停地面 / 到达后均不显示
      var remainingRoutes = []
      for (var ri = 0; ri < this._routeLines.length; ri++) {
        var r = this._routeLines[ri]
        var item = renderMap[r.flightData.id]
        if (item && item.isAirborne) {
          var tp = self._calcTimeProgress(item.f)
          if (tp != null && tp >= 0.995) {
            self._removeFlightEntry(r)
          } else {
            remainingRoutes.push(r)
          }
        } else {
          this._removeFlightEntry(r)
        }
      }

      // 飞机：取消不生成；空中按时间推进；延误未起飞停地面
      var remainingPlanes = []
      for (var pi = 0; pi < this._planeInstances.length; pi++) {
        var p = this._planeInstances[pi]
        var item2 = renderMap[p.flightData.id]
        if (!item2 || item2.isCancelled) {
          this._removePlaneInstance(p)
          continue
        }

        if (item2.grounded) {
          p.grounded = true
          p.targetProgress = 0
          p.flightData.progress = 0
          p.progress = 0
        } else {
          p.grounded = false
          var tp2 = self._calcTimeProgress(item2.f)
          if (tp2 != null) {
            if (tp2 >= 0.995) {
              self._removePlaneInstance(p)
              continue
            }
            if (tp2 > p.targetProgress) {
              p.targetProgress = tp2
              p.flightData.progress = tp2
            }
          } else {
            var sp = item2.f.progress
            if (sp != null) {
              if (sp > 2) sp = sp / 100
              if (sp > p.targetProgress) {
                p.targetProgress = sp
                p.flightData.progress = sp
              }
            }
          }
        }
        remainingPlanes.push(p)
      }
      this._routeLines = remainingRoutes
      this._planeInstances = remainingPlanes

      // 为新的渲染航班创建航线和飞机
      var existingRouteIds = {}
      remainingRoutes.forEach(function(r) { existingRouteIds[r.flightData.id] = true })
      var existingPlaneIds = {}
      remainingPlanes.forEach(function(p) { existingPlaneIds[p.flightData.id] = true })

      for (var id in renderMap) {
        var item = renderMap[id]
        var f = item.f

        var depCity = f.dep_airport || f.departure_airport || f.from || ''
        var arrCity = f.arr_airport || f.arrival_airport || f.to || ''

        var depCoord = (f.dep_lng && f.dep_lat) ? [f.dep_lng, f.dep_lat] : getCityCoord(depCity)
        var arrCoord = (f.arr_lng && f.arr_lat) ? [f.arr_lng, f.arr_lat] : getCityCoord(arrCity)

        if (!depCoord || !arrCoord) continue

        var status = item.isCancelled ? 'cancelled'
          : (item.isAirborne || item.grounded) && f.is_delayed ? 'delayed'
          : 'flying'

        var progress = 0
        if (item.isAirborne) {
          progress = self._calcTimeProgress(f)
          if (progress == null) {
            progress = f.progress
            if (progress == null) {
              progress = 0.05 + Math.random() * 0.9
            } else {
              if (progress > 2) progress = progress / 100
              progress = Math.max(0.01, Math.min(1, progress))
            }
          }
          if (progress >= 0.995) continue
        }

        var flightData = {
          id: id,
          flightNo: f.flight_no || f.flightNo || ('FL' + id),
          ac_type: f.ac_type || (f.aircraft_type || 'A320'),
          depCity: depCity,
          arrCity: arrCity,
          depLng: depCoord[0],
          depLat: depCoord[1],
          arrLng: arrCoord[0],
          arrLat: arrCoord[1],
          progress: progress,
          status: status,
          altitude: f.altitude || 8000,
          speed: f.speed || 800,
          _raw: f,
        }

        var routeEntry = null
        if (item.isAirborne) {
          if (!existingRouteIds[id]) {
            routeEntry = self._createRouteArc(flightData)
          } else {
            routeEntry = self._routeLines.find(function(r) { return r.flightData.id === id })
          }
        } else if (item.grounded) {
          // 延误未起飞：只生成曲线用于把飞机停在起飞机场，不显示航线轮廓
          routeEntry = { curve: self._buildCurve(flightData), flightData: flightData }
        }

        if (!item.isCancelled && !existingPlaneIds[id] && routeEntry) {
          var inst = self._createPlaneInstance(flightData, routeEntry)
          if (inst && item.grounded) {
            inst.grounded = true
          }
        }
      }
    },

    /* ==================== 交互 ==================== */
    _onMouseClick: function(event) {
      var el = this.$refs.container
      if (!el || !this._camera) return

      var rect = el.getBoundingClientRect()
      this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

      this._raycaster.setFromCamera(this._mouse, this._camera)

      var self = this
      var lineObjects = this._routeLines.map(function(r) { return r.line })
      var intersects = this._raycaster.intersectObjects(lineObjects)

      if (intersects.length > 0) {
        var obj = intersects[0].object
        if (obj.userData && obj.userData.flightData) {
          this._selectedObject = obj
          this._selectedFlightId = obj.userData.flightData.id
          this._resetAllHighlights()
          obj.material.opacity = 1.0
          obj.material.color.set(0xffffff)
          var routeEntry = this._routeLines.find(function(r) { return r.line === obj })
          if (routeEntry && routeEntry.glowGroup) {
            routeEntry.glowGroup.children.forEach(function(c) { if (c.material) c.material.opacity = 0.5 })
          }
          this.$emit('flightClick', obj.userData.flightData)
          return
        }
      }

      var markerObjects = this._airportMarkers.map(function(m) { return m.group })
      var markerIntersects = this._raycaster.intersectObjects(markerObjects, true)
      if (markerIntersects.length > 0) {
        var mobj = markerIntersects[0].object
        while (mobj) {
          if (mobj.userData && mobj.userData.cityName) {
            this.$emit('flightClick', { airport: mobj.userData.cityName })
            return
          }
          mobj = mobj.parent
        }
      }

      this._resetAllHighlights()
      this._selectedObject = null
    },

    _onMouseMove: function(event) {
      var el = this.$refs.container
      if (!el || !this._camera) return
      var rect = el.getBoundingClientRect()
      this._mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
      this._mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1

      this._raycaster.setFromCamera(this._mouse, this._camera)
      var self = this
      var lineObjects = this._routeLines.map(function(r) { return r.line })
      var intersects = this._raycaster.intersectObjects(lineObjects)

      if (intersects.length > 0) {
        var obj = intersects[0].object
        if (obj !== this._hoveredObject && obj.userData && obj.userData.flightData) {
          this._resetHover()
          this._hoveredObject = obj
          obj.material.opacity = 0.9
          obj.material.color.set(0xffcc00)
          this.$emit('flightHover', obj.userData.flightData)
          el.style.cursor = 'pointer'
        }
      } else {
        if (this._hoveredObject) {
          this._resetHover()
          el.style.cursor = ''
        }
      }
    },

    _onMouseDoubleClick: function(event) {
      var self = this
      var sel = this._selectedObject
      if (!sel || !sel.userData || !sel.userData.flightData) return

      var fd = sel.userData.flightData
      var midLng = (fd.depLng + fd.arrLng) / 2
      var midLat = (fd.depLat + fd.arrLat) / 2
      var pos = lngLatToWorld(midLng, midLat)
      pos.x *= MAP_SCALE
      pos.z *= MAP_SCALE

      var targetPos = new THREE.Vector3(pos.x, 8, pos.z + 6)
      var startPos = this._camera.position.clone()
      var startTarget = this._controls.target.clone()
      var endTarget = new THREE.Vector3(pos.x, 0, pos.z)

      var duration = 800
      var startTime = performance.now()
      var controls = this._controls
      var camera = this._camera

      function animateCamera(timestamp) {
        var elapsed = timestamp - startTime
        var t = Math.min(elapsed / duration, 1.0)
        var ease = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2

        camera.position.lerpVectors(startPos, targetPos, ease)
        controls.target.lerpVectors(startTarget, endTarget, ease)
        controls.update()

        if (t < 1) {
          requestAnimationFrame(animateCamera)
        }
      }
      requestAnimationFrame(animateCamera)
    },

    _resetAllHighlights: function() {
      this._routeLines.forEach(function(r) {
        if (r.line && r.line.material) {
          var color = STATUS_COLORS[r.flightData.status] || STATUS_COLORS.flying
          r.line.material.opacity = 0.55
          r.line.material.color.set(color)
        }
      })
    },

    _resetHover: function() {
      if (this._hoveredObject && this._hoveredObject.userData && this._hoveredObject.userData.flightData) {
        var fd = this._hoveredObject.userData.flightData
        var color = STATUS_COLORS[fd.status] || STATUS_COLORS.flying
        this._hoveredObject.material.opacity = 0.55
        this._hoveredObject.material.color.set(color)
      }
      this._hoveredObject = null
    },

    /* ==================== 动画循环 ==================== */
    _animate: function(time) {
      var self = this
      this._animationId = requestAnimationFrame(function(t) { self._animate(t) })
      var dt = Math.min(this._clock.getDelta(), 0.1)

      this._controls.update()

      this._planeInstances.forEach(function(inst) {
        if (inst.grounded) {
          // 延误未起飞：飞机停在地面（航线弧起点），不随进度移动
          var gpt = inst.curve.getPoint(0)
          inst.group.position.copy(gpt).multiplyScalar(MAP_SCALE)
          return
        }

        var target = inst.targetProgress
        if (target == null) target = 0.03
        target = Math.min(target, 0.999)
        var gap = target - inst.progress

        if (gap > 0.0005) {
          // 时间目标在前，平滑趋近
          inst.progress += gap * Math.min(dt * 1.5, 0.3)
        } else {
          // 目标接近，微量自驱防止卡帧
          inst.progress += dt * 0.002
        }
        if (inst.progress > 0.999) inst.progress = 0.999

        var pt = inst.curve.getPoint(Math.min(inst.progress, 0.999))
        inst.group.position.copy(pt).multiplyScalar(MAP_SCALE)

        var nextPt = inst.curve.getPoint(Math.min(inst.progress + 0.01, 0.999))
        var dir = new THREE.Vector3().subVectors(nextPt, pt).normalize()
        if (dir.length() > 0.001) {
          // 用右手坐标系构造朝向：+Z = 前进方向, +Y 尽量保持向上
          var worldUp = new THREE.Vector3(0, 1, 0)
          // right = up × forward（先叉乘 up 再 forward，得到右侧）
          var right = new THREE.Vector3().crossVectors(worldUp, dir)
          if (right.length() < 0.0001) {
            // dir 与 up 平行（直上直下），用 X 轴作 right
            right.set(1, 0, 0)
          }
          right.normalize()
          // 重新计算真正的 up = forward × right
          var realUp = new THREE.Vector3().crossVectors(dir, right).normalize()

          var m4 = new THREE.Matrix4()
          m4.makeBasis(right, realUp, dir)
          var quat = new THREE.Quaternion().setFromRotationMatrix(m4)

          // 各机型模型已在 _normalizePlaneModel 中统一为「机头朝 +Z」，
          // 与前进方向一致，无需再做预旋转修正
          inst.group.quaternion.slerp(quat, Math.min(dt * 8, 1))
        }
      })
      // 备选清理：动画发现进度到位但 _updateFlights 未及时清理的飞机
      var alivePlanes2 = []
      for (var ai = 0; ai < self._planeInstances.length; ai++) {
        var ap = self._planeInstances[ai]
        var tp = self._calcTimeProgress(ap.flightData._raw)
        if (ap.progress >= 0.999 && (tp == null || tp >= 0.995)) {
          // 移除对应航线
          for (var rj = self._routeLines.length - 1; rj >= 0; rj--) {
            if (self._routeLines[rj].flightData.id === ap.flightData.id) {
              self._removeFlightEntry(self._routeLines[rj])
              self._routeLines.splice(rj, 1)
              break
            }
          }
          self._removePlaneInstance(ap)
        } else {
          alivePlanes2.push(ap)
        }
      }
      self._planeInstances = alivePlanes2

      // 仪表数据：为选中的航班计算实时飞行参数
      if (self._selectedFlightId) {
        var selPlane = null
        for (var si = 0; si < self._planeInstances.length; si++) {
          if (self._planeInstances[si].flightData.id === self._selectedFlightId) {
            selPlane = self._planeInstances[si]
            break
          }
        }
        if (selPlane) {
          var pt = selPlane.curve.getPoint(Math.min(selPlane.progress, 0.999))
          var nextPt = selPlane.curve.getPoint(Math.min(selPlane.progress + 0.005, 0.999))
          var dir = new THREE.Vector3().subVectors(nextPt, pt).normalize()
          var heading = Math.atan2(dir.x, dir.z) * 180 / Math.PI
          if (heading < 0) heading += 360

          // 高度：从世界 Y 反算为英尺（对应 _createRouteArc 中 *0.4 缩放）
          var altMeters = pt.y * 900 / 0.4
          var altFt = Math.round(altMeters * 3.28084)

          // 升降率：帧间高度变化
          var prevAlt = selPlane._prevAltY || pt.y
          var vsMps = ((pt.y - prevAlt) / Math.max(dt, 0.001)) * 900 / 0.4 * 3.28084 * 60  // ft/min
          selPlane._prevAltY = pt.y

          // 俯仰角：方向向量的 Y 分量
          var pitch = Math.asin(Math.max(-0.9, Math.min(0.9, dir.y))) * 180 / Math.PI

          // 横滚：从水平方向变化率估算
          var hdgDiff = heading - (selPlane._prevHdg || heading)
          if (hdgDiff > 180) hdgDiff -= 360
          if (hdgDiff < -180) hdgDiff += 360
          var roll = Math.max(-30, Math.min(30, hdgDiff * 3))
          selPlane._prevHdg = heading

          // 剩余时间
          var fd = selPlane.flightData
          var remain = 0
          if (fd._raw && fd._raw.scheduled_dep && fd._raw.scheduled_arr) {
            var dep = fd._raw.scheduled_dep, arr = fd._raw.scheduled_arr
            var ttl = new Date(arr[0], arr[1]-1, arr[2], arr[3]||0, arr[4]||0).getTime()
              - new Date(dep[0], dep[1]-1, dep[2], dep[3]||0, dep[4]||0).getTime()
            remain = ttl / 60000 * (1 - selPlane.progress)  // minutes
          }

          // 剩余距离
          var dx2 = fd._arrPos.x - pt.x, dz2 = fd._arrPos.z - pt.z
          var distRemain = Math.sqrt(dx2 * dx2 + dz2 * dz2) * 111  // rough km

          self.$emit('instrumentData', {
            flightNo: fd.flightNo,
            speed: fd.speed || 800,
            heading: heading,
            altitude: altFt,
            verticalSpeed: vsMps,
            pitch: pitch,
            roll: roll,
            progress: selPlane.progress,
            cruiseAlt: fd._cruiseAlt ? Math.round(fd._cruiseAlt * 3.28084) : 35000,
            timeRemaining: remain,
            distanceRemaining: Math.round(distRemain),
            phaseBreaks: fd._phaseBreaks || { climbEnd: 0.16, cruiseEnd: 0.84 },
          })
        }
      }

      var pulsePhase = time * 0.002
      this._airportMarkers.forEach(function(m, i) {
        var s = 1 + Math.sin(pulsePhase + i * 0.5) * 0.15
        if (m.group.children[1]) {
          m.group.children[1].scale.setScalar(s)
        }
      })

      this._renderer.render(this._scene, this._camera)
    },

    _onResize: function() {
      var el = this.$refs.container
      if (!el || !this._renderer) return
      var w = el.clientWidth
      var h = el.clientHeight
      this._renderer.setSize(w, h)
      this._camera.aspect = w / Math.max(h, 1)
      this._camera.updateProjectionMatrix()
    },

    /* ==================== 场景初始化 ==================== */
    _initScene: function() {
      var self = this
      var el = this.$refs.container
      if (!el) return
      var w = el.clientWidth, h = el.clientHeight

      // Renderer
      this._renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
      this._renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
      this._renderer.setSize(w, h)
      this._renderer.shadowMap.enabled = true
      this._renderer.shadowMap.type = THREE.PCFSoftShadowMap
      this._renderer.toneMapping = THREE.ACESFilmicToneMapping
      this._renderer.toneMappingExposure = 1.1
      el.appendChild(this._renderer.domElement)

      // Scene
      this._scene = new THREE.Scene()
      this._scene.background = new THREE.Color(0x1a1a2e)
      this._scene.fog = new THREE.FogExp2(0x1a1a2e, 0.000025)

      // 地图放大组：地形 / 机场标记 / 航线弧统一放入该组并放大 MAP_SCALE 倍；
      // 飞机模型不加进该组（保持原尺寸），只在定位时乘以 MAP_SCALE
      this._mapGroup = new THREE.Group()
      this._mapGroup.scale.setScalar(MAP_SCALE)
      this._scene.add(this._mapGroup)

      // Camera
      this._camera = new THREE.PerspectiveCamera(50, w / Math.max(h, 1), 1, 3000)
      this._camera.position.set(0, 180, 120)
      this._camera.lookAt(0, 0, 0)

      // OrbitControls
      this._controls = new OrbitControls(this._camera, this._renderer.domElement)
      this._controls.enableDamping = true
      this._controls.dampingFactor = 0.08
      this._controls.minDistance = 60
      this._controls.maxDistance = 1000
      this._controls.maxPolarAngle = Math.PI * 0.68
      this._controls.minPolarAngle = 0.05
      this._controls.zoomSpeed = 2.5
      this._controls.target.set(0, 0, 0)
      this._controls.update()

      // Lighting
      this._scene.add(new THREE.AmbientLight(0x888899, 0.7))
      var sun = new THREE.DirectionalLight(0xffffff, 0.8)
      sun.position.set(100, 200, 50)
      sun.castShadow = true
      sun.shadow.mapSize.set(1024, 1024)
      sun.shadow.camera.near = 1
      sun.shadow.camera.far = 800
      sun.shadow.camera.left = -400
      sun.shadow.camera.right = 400
      sun.shadow.camera.top = 400
      sun.shadow.camera.bottom = -400
      this._scene.add(sun)
      this._scene.add(new THREE.DirectionalLight(0x445577, 0.3))

      // 初始化数据结构
      this._routeLines = []
      this._planeInstances = []
      this._airportMarkers = []
      this._planeModels = null
      this._raycaster = new THREE.Raycaster()
      this._mouse = new THREE.Vector2()
      this._hoveredObject = null
      this._selectedObject = null
      this._clock = new THREE.Clock()

      // 中国地图纹理
      this.loadingText = '加载地图数据...'
      this._createChinaTextures()

      // 地形地面
      this._createTerrainGround()

      // 机场标记
      this._createAllAirportMarkers()

      // 加载飞机模型（按机型 A319/A320/A321 对齐）
      this._loadPlaneModels().then(function() {
        self.loadingText = '加载航班数据...'
        self._updateFlights(self.flights)

        // 鼠标事件
        self._renderer.domElement.addEventListener('click', function(e) { self._onMouseClick(e) })
        self._renderer.domElement.addEventListener('mousemove', function(e) { self._onMouseMove(e) })
        self._renderer.domElement.addEventListener('dblclick', function(e) { self._onMouseDoubleClick(e) })
        window.addEventListener('resize', function() { self._onResize() })

        self.sceneReady = true
        self._animate(0)
      })
    },
  },

  mounted: function() {
    this._initScene()
  },

  beforeDestroy: function() {
    window.removeEventListener('resize', this._onResize)
    if (this._animationId) cancelAnimationFrame(this._animationId)

    var self = this
    this._routeLines.forEach(function(r) {
      if (r.line) { r.line.geometry.dispose(); r.line.material.dispose() }
      if (r.glowGroup) {
        r.glowGroup.children.forEach(function(c) { c.geometry.dispose(); c.material.dispose() })
      }
    })
    this._planeInstances.forEach(function(p) {
      p.group.traverse(function(c) { if (c.geometry) c.geometry.dispose(); if (c.material) c.material.dispose() })
    })
    this._airportMarkers.forEach(function(m) {
      m.group.traverse(function(c) { if (c.geometry) c.geometry.dispose(); if (c.material) c.material.dispose() })
    })
    if (this._chinaMaskTex) this._chinaMaskTex.dispose()
    if (this._chinaMapTex) this._chinaMapTex.dispose()
    if (this._terrainTex) this._terrainTex.dispose()
    if (this._renderer) {
      this._renderer.dispose()
      var el = this.$refs.container
      if (el && this._renderer.domElement) {
        el.removeChild(this._renderer.domElement)
      }
    }
  },
}
</script>

<style scoped>
.flight3d-container {
  width: 100%;
  height: 100%;
  overflow: hidden;
  position: relative;
  background: #1a1a2e;
}

.flight3d-loading {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(10, 10, 26, 0.92);
  z-index: 100;
  color: #8a8aaa;
  font-size: 14px;
  gap: 16px;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(64, 158, 255, 0.2);
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
