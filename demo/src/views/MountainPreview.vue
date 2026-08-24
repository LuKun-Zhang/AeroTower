<template>
  <div class="preview-container" ref="container"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'

const container = ref(null)
let renderer, scene, camera, controls, animationId

const models = [
  { file: 'Mountain with Snow by Matthew Creighton - 0VBAQNbpNcl.glb', label: '雪山' },
  { file: 'Mountain by Poly by Google - 099f6GxB1bj.glb',     label: '绿山' },
  { file: 'Mountains by Quaternius - w9VBrh7Nz0.glb',         label: '群山' },
]

function loadGLB(path) {
  return new Promise((resolve, reject) => {
    new GLTFLoader().load(
      `/models/${path}`,
      (gltf) => resolve(gltf.scene),
      (p) => { if (p.total) console.log(`${path}: ${Math.round(p.loaded/p.total*100)}%`) },
      reject
    )
  })
}

function createLighting() {
  scene.add(new THREE.AmbientLight(0x888899, 0.5))
  const sun = new THREE.DirectionalLight(0xffffff, 1.5)
  sun.position.set(20, 30, 25)
  scene.add(sun)
  const fill = new THREE.DirectionalLight(0x889966, 0.35)
  fill.position.set(-15, 10, -10)
  scene.add(fill)
}

function autoScale(obj, targetHeight = 5) {
  const box = new THREE.Box3().setFromObject(obj)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const scale = targetHeight / size.y
  obj.scale.setScalar(scale)
  obj.position.sub(center.multiplyScalar(scale))
  return { scale, size }
}

async function initScene() {
  const el = container.value
  if (!el) return

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(el.clientWidth, el.clientHeight)
  renderer.shadowMap.enabled = true
  renderer.shadowMap.type = THREE.PCFSoftShadowMap
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.1
  el.appendChild(renderer.domElement)

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x87ceeb)
  scene.fog = new THREE.Fog(0x87ceeb, 40, 120)

  camera = new THREE.PerspectiveCamera(55, el.clientWidth / el.clientHeight, 0.5, 200)
  camera.position.set(8, 6, 14)
  camera.lookAt(0, 2, 0)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.target.set(0, 2, 0)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.minDistance = 3
  controls.maxDistance = 60
  controls.maxPolarAngle = Math.PI * 0.48

  createLighting()

  // 大地平面
  const groundGeo = new THREE.PlaneGeometry(60, 60)
  const groundMat = new THREE.MeshPhongMaterial({ color: 0x558844 })
  const ground = new THREE.Mesh(groundGeo, groundMat)
  ground.rotation.x = -Math.PI / 2
  ground.position.y = -4
  scene.add(ground)

  // 分别加载三座山
  const spacing = 7
  for (let i = 0; i < models.length; i++) {
    try {
      const obj = await loadGLB(models[i].file)
      const { scale, size } = autoScale(obj, 5)
      obj.position.x = (i - 1) * spacing

      obj.traverse(child => {
        if (child.isMesh) {
          child.castShadow = true
          child.receiveShadow = true
        }
      })

      scene.add(obj)
      console.log(`${models[i].label} 加载成功 (${size.x.toFixed(1)}x${size.y.toFixed(1)}x${size.z.toFixed(1)}, 缩放${scale.toFixed(2)})`)

      // 标签
      const canvas = document.createElement('canvas')
      canvas.width = 256; canvas.height = 64
      const ctx = canvas.getContext('2d')
      ctx.fillStyle = 'rgba(0,0,0,0.65)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.font = 'bold 28px Arial'
      ctx.textAlign = 'center'
      ctx.fillStyle = '#fff'
      ctx.fillText(models[i].label, 128, 42)
      const tex = new THREE.CanvasTexture(canvas)
      tex.minFilter = THREE.LinearFilter
      const labelMat = new THREE.SpriteMaterial({ map: tex, transparent: true })
      const labelSprite = new THREE.Sprite(labelMat)
      labelSprite.scale.set(3.5, 0.88, 1)
      labelSprite.position.set((i - 1) * spacing, 5.5, 0)
      scene.add(labelSprite)
    } catch (err) {
      console.error(`${models[i].label} 加载失败:`, err)
      const failGeo = new THREE.ConeGeometry(2, 5, 6)
      const failMat = new THREE.MeshPhongMaterial({ color: 0xff4444, wireframe: true })
      const failBox = new THREE.Mesh(failGeo, failMat)
      failBox.position.x = (i - 1) * spacing
      scene.add(failBox)
    }
  }

  window.addEventListener('resize', onResize)
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

onMounted(() => initScene())

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
  width: 100%; height: 100vh; overflow: hidden;
  background: #87ceeb;
}
</style>
