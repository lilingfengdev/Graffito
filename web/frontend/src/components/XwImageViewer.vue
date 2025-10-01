<template>
  <div class="xw-image-viewer">
    <div class="image-list" :class="gridClass">
      <div
        v-for="(image, index) in images"
        :key="index"
        class="image-item"
        :class="{ 'clickable': previewable }"
        @click="handlePreview(index)"
      >
        <el-image
          :src="image.url || image"
          :alt="image.alt || `图片${index + 1}`"
          :fit="fit"
          :lazy="lazy"
          :class="imageClass"
          :style="imageStyle"
        >
          <template #placeholder>
            <div class="image-placeholder">
              <el-icon class="loading-icon"><Loading /></el-icon>
            </div>
          </template>
          <template #error>
            <div class="image-error">
              <el-icon><PictureFilled /></el-icon>
              <span>加载失败</span>
            </div>
          </template>
        </el-image>
        
        <div v-if="image.title" class="image-title">
          {{ image.title }}
        </div>
        
        <div v-if="showMask" class="image-mask">
          <div class="mask-actions">
            <el-icon @click.stop="handlePreview(index)"><ZoomIn /></el-icon>
            <el-icon v-if="downloadable" @click.stop="handleDownload(image)"><Download /></el-icon>
            <el-icon v-if="deletable" @click.stop="handleDelete(index)"><Delete /></el-icon>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Element Plus Image Viewer -->
    <el-image-viewer
      v-if="showViewer"
      :url-list="urlList"
      :initial-index="currentIndex"
      :hide-on-click-modal="true"
      :teleported="true"
      @close="showViewer = false"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElImageViewer } from 'element-plus'
import { Loading, PictureFilled, ZoomIn, Download, Delete } from '@element-plus/icons-vue'

const props = defineProps({
  images: {
    type: Array,
    required: true,
    default: () => []
  },
  columns: {
    type: Number,
    default: 4,
    validator: (value) => value >= 1 && value <= 12
  },
  gap: {
    type: Number,
    default: 12
  },
  fit: {
    type: String,
    default: 'cover',
    validator: (value) => ['fill', 'contain', 'cover', 'none', 'scale-down'].includes(value)
  },
  width: {
    type: [Number, String],
    default: 'auto'
  },
  height: {
    type: [Number, String],
    default: 200
  },
  borderRadius: {
    type: [Number, String],
    default: 8
  },
  previewable: {
    type: Boolean,
    default: true
  },
  downloadable: {
    type: Boolean,
    default: false
  },
  deletable: {
    type: Boolean,
    default: false
  },
  showMask: {
    type: Boolean,
    default: true
  },
  lazy: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['preview', 'download', 'delete'])

const showViewer = ref(false)
const currentIndex = ref(0)

const gridClass = computed(() => `grid-cols-${props.columns}`)

const imageClass = computed(() => [
  'xw-image',
  {
    'xw-image-hoverable': props.previewable
  }
])

const imageStyle = computed(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width,
  height: typeof props.height === 'number' ? `${props.height}px` : props.height,
  borderRadius: typeof props.borderRadius === 'number' ? `${props.borderRadius}px` : props.borderRadius
}))

const urlList = computed(() => {
  return props.images.map(img => img.url || img)
})

const handlePreview = (index) => {
  if (!props.previewable) return
  
  currentIndex.value = index
  showViewer.value = true
  emit('preview', index, props.images[index])
}

const handleDownload = (image) => {
  const url = image.url || image
  const link = document.createElement('a')
  link.href = url
  link.download = image.name || url.split('/').pop() || 'download'
  link.click()
  emit('download', image)
}

const handleDelete = (index) => {
  emit('delete', index, props.images[index])
}
</script>

<style scoped>
.xw-image-viewer {
  width: 100%;
}

.image-list {
  display: grid;
  gap: v-bind('`${gap}px`');
}

.grid-cols-1 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
.grid-cols-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid-cols-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid-cols-4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.grid-cols-5 { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.grid-cols-6 { grid-template-columns: repeat(6, minmax(0, 1fr)); }

.image-item {
  position: relative;
  overflow: hidden;
  border-radius: var(--xw-radius-lg);
  transition: var(--xw-transition);
}

.image-item.clickable {
  cursor: pointer;
}

.image-item:hover {
  transform: translateY(-2px);
  box-shadow: var(--xw-shadow-lg);
}

.xw-image {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: inherit;
}

.xw-image-hoverable:hover {
  transform: scale(1.05);
}

.image-placeholder,
.image-error {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--xw-bg-secondary);
  color: var(--xw-text-tertiary);
  gap: var(--xw-space-2);
}

.loading-icon {
  font-size: 32px;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.image-title {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: var(--xw-space-2) var(--xw-space-3);
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7), transparent);
  color: white;
  font-size: var(--xw-text-sm);
  text-align: center;
}

.image-mask {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: var(--xw-transition);
}

.image-item:hover .image-mask {
  opacity: 1;
}

.mask-actions {
  display: flex;
  gap: var(--xw-space-4);
}

.mask-actions .el-icon {
  font-size: 24px;
  color: white;
  cursor: pointer;
  padding: var(--xw-space-2);
  border-radius: var(--xw-radius);
  background: rgba(255, 255, 255, 0.1);
  transition: var(--xw-transition);
}

.mask-actions .el-icon:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scale(1.1);
}

/* 响应式 */
@media (max-width: 1024px) {
  .grid-cols-4 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .grid-cols-5 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .grid-cols-6 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 768px) {
  .grid-cols-3,
  .grid-cols-4,
  .grid-cols-5,
  .grid-cols-6 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 480px) {
  .image-list { gap: var(--xw-space-2); }
  .grid-cols-2,
  .grid-cols-3,
  .grid-cols-4,
  .grid-cols-5,
  .grid-cols-6 { grid-template-columns: repeat(1, minmax(0, 1fr)); }
}
</style>
