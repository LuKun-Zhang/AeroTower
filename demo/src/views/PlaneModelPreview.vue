<template>
  <div class="preview-container" ref="container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js'

const container = ref(null)
let renderer, scene, camera, controls, animationId

function loadGLBModel() {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader()

    // 可选：DRACO 解压缩支持
    const dracoLoader = new DRACOLoader()
    dracoLoader.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/')
    loader.setDRACOLoader(dracoLoader)

    loader.load(
      '/models/A320.glb',
      (gltf) => {
        resolve(gltf.scene)
      },
      (progress) => {
        const pct = Math.round((progress.loaded / progress.total) * 100)
        console.log(`GLB 加载: ${pct}%`)
      },
      (error) => {
        console.error('GLB 加载失败:', error)
        reject(error)
      }
    )
  })
}

function createLighting() {
  // 环境光
  scene.add(new THREE.AmbientLight(0x666688, 0.6))

  // 主方向光（模拟太阳）
  const sun = new THREE.DirectionalLight(0xffffff, 1.2)
  sun.position.set(10, 15, 8)
  scene.add(sun)

  // 补光（底部）
  const fill = new THREE.DirectionalLight(0x8899cc, 0.4)
  fill.position.set(-5, -2, -3)
  scene.add(fill)

  // 背光（轮廓光）
  const rim = new THREE.DirectionalLight(0xaaccff, 0.5)
  rim.position.set(0, 0, -10)
  scene.add(rim)

  // 点光源（高光）
  const spot = new THREE.PointLight(0xffffff, 0.3, 30)
  spot.position.set(5, 8, 5)
  scene.add(spot)
}

function createGrid() {
  const grid = new THREE.GridHelper(20, 20, 0x334466, 0x223355)
  grid.position.y = -2
  scene.add(grid)
}

async function initScene() {
  const el = container.value
  if (!el) return

  // 渲染器
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(el.clientWidth, el.clientHeight)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  el.appendChild(renderer.domElement)

  // 场景
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x1a1a2e)
  scene.fog = new THREE.Fog(0x1a1a2e, 15, 40)

  // 相机
  camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.5, 100)
  camera.position.set(6, 3, 8)
  camera.lookAt(0, 0, 3)

  // OrbitControls
  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 0, 3)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 3
  controls.maxDistance = 20
  controls.maxPolarAngle = Math.PI * 0.7

  // 灯光
  createLighting()

  // 参考网格
  createGrid()

  // 加载 GLB 飞机模型
  try {
    const plane = await loadGLBModel()

    // 自动缩放到合适大小
    const box = new THREE.Box3().setFromObject(plane)
    const size = box.getSize(new THREE.Vector3())
    const center = box.getCenter(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, size.z)
    const targetSize = 8
    const scale = targetSize / maxDim
    plane.scale.setScalar(scale)
    plane.position.set(-center.x * scale, -center.y * scale, -center.z * scale + 3)

    scene.add(plane)
    console.log('A320 模型加载成功, 尺寸:', size, '缩放:', scale.toFixed(3))
  } catch (err) {
    console.error('模型加载失败:', err)
    // 加载失败时显示一个占位立方体
    const failGeo = new THREE.BoxGeometry(3, 1, 1.5, 4, 4, 4)
    const failMat = new THREE.MeshPhongMaterial({ color: 0xff4444, wireframe: true })
    const failBox = new THREE.Mesh(failGeo, failMat)
    failBox.position.set(0, 0, 3)
    scene.add(failBox)
  }

  // 发光底座
  const baseGeo = new THREE.RingGeometry(1.8, 2.0, 64)
  const baseMat = new THREE.MeshBasicMaterial({ color: 0x4488cc, side: THREE.DoubleSide, transparent: true, opacity: 0.15 })
  const base = new THREE.Mesh(baseGeo, baseMat)
  base.rotation.x = -Math.PI / 2
  base.position.y = -1.9
  scene.add(base)

  // 自适应
  window.addEventListener('resize', onResize)

  // 渲染循环
  animate()
}

function onResize() {
  const el = container.value
  if (!el || !camera || !renderer) return
  camera.aspect = el.clientWidth / el.clientHeight
  camera.updateProjectionMatrix()
  renderer.setSize(el.clientWidth, el.clientHeight)
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

onMounted(() => {
  initScene()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(animationId)
  window.removeEventListener('resize', onResize)
  renderer?.dispose()
  if (container.value && renderer?.domElement) {
    container.value.removeChild(renderer.domElement)
  }
})
</script>

<style scoped>
.preview-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
  background: #1a1a2e;
}
</style>
