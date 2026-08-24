<template>
  <div class="pdf-doc">
    <!-- 工具栏 -->
    <div class="pdf-toolbar">
      <span class="pdf-title"><i class="el-icon-document"></i> {{ title }}</span>
      <span v-if="page" class="pdf-loc"><i class="el-icon-location"></i> 已定位至第 {{ page }} 页（对应条款）</span>
      <span v-else class="pdf-meta">PDF 官方文档 · 内嵌浏览</span>
      <div class="pdf-actions">
        <el-button size="mini" icon="el-icon-view" @click="openWindow">新窗口查看</el-button>
        <el-button size="mini" type="primary" icon="el-icon-download" @click="download">下载</el-button>
      </div>
    </div>

    <!-- PDF 内嵌浏览 -->
    <div class="pdf-frame-wrap">
      <iframe
        :key="pdfSrc"
        :src="pdfSrc"
        class="pdf-frame"
        @load="onFrameLoad"
      ></iframe>
      <div v-if="loading" class="pdf-loading">
        <i class="el-icon-loading"></i>
        <span>文档加载中，请稍候…</span>
      </div>
      <div v-if="frameFailed" class="pdf-fallback">
        <i class="el-icon-warning-outline"></i>
        <p>浏览器无法在此页内嵌显示该 PDF（部分政府站点禁止跨域嵌入）。</p>
        <p>
          <el-button type="primary" size="small" @click="openWindow">在新窗口打开查看</el-button>
          <el-button size="small" @click="download">下载后本地查看</el-button>
        </p>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * PDF 文档浏览组件
 * 基于浏览器原生 PDF Viewer 内嵌展示官方 PDF；支持新窗口打开与下载。
 * 若目标站点禁止跨域嵌入，自动降级为「新窗口/下载」提示。
 */
export default {
  name: 'PdfDoc',
  props: {
    src: { type: String, required: true },
    title: { type: String, default: '官方文档' },
    // PDF 物理页号（1 起），通过 #page=N 让浏览器直接跳到对应条款页
    page: { type: Number, default: null },
  },
  data() {
    return {
      loading: true,
      frameFailed: false,
      timer: null,
    }
  },
  computed: {
    pdfSrc() {
      return this.page ? `${this.src}#page=${this.page}` : this.src
    },
  },
  watch: {
    src() {
      this.reset()
    },
    page() {
      this.reset()
    },
  },
  mounted() {
    this.reset()
  },
  beforeDestroy() {
    if (this.timer) clearTimeout(this.timer)
  },
  methods: {
    reset() {
      this.loading = true
      this.frameFailed = false
      if (this.timer) clearTimeout(this.timer)
      // 本地 PDF 一般数秒内完成；30 秒超时兜底（大文件/慢网络），
      // iframe 以 :key 绑定 src，src（含 #page 锚点）变化必然重建并触发 load
      this.timer = setTimeout(() => {
        if (this.loading) this.frameFailed = true
      }, 30000)
    },
    onFrameLoad() {
      this.loading = false
      if (this.timer) clearTimeout(this.timer)
    },
    openWindow() {
      window.open(this.src, '_blank', 'noopener')
    },
    download() {
      const a = document.createElement('a')
      a.href = this.src
      a.target = '_blank'
      a.rel = 'noopener'
      a.download = ''
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    },
  },
}
</script>

<style scoped>
.pdf-doc {
  border: 1px solid #e4e7ed; border-radius: 8px; overflow: hidden; background: #fff;
}
.pdf-toolbar {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 14px; background: #f5f7fa; border-bottom: 1px solid #e4e7ed;
}
.pdf-title { font-size: 13px; font-weight: 600; color: #303133; display: flex; align-items: center; gap: 6px; }
.pdf-title i { color: #f56c6c; }
.pdf-meta { font-size: 11px; color: #909399; }
.pdf-loc { font-size: 11px; color: #409eff; display: flex; align-items: center; gap: 4px; }
.pdf-loc i { font-size: 12px; }
.pdf-actions { margin-left: auto; display: flex; gap: 8px; }
.pdf-frame-wrap { position: relative; height: 620px; background: #525659; }
.pdf-frame { width: 100%; height: 100%; border: none; }
.pdf-loading {
  position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 10px; color: #dcdfe6; font-size: 13px;
  background: #525659; z-index: 2;
}
.pdf-loading i { font-size: 28px; }
.pdf-fallback {
  position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 8px; color: #e6e8eb; text-align: center; font-size: 13px;
  background: #525659; padding: 24px; z-index: 3;
}
.pdf-fallback i { font-size: 34px; color: #e6a23c; }
.pdf-fallback p { margin: 4px 0; }
</style>
