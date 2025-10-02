<template>
  <el-image
    :src="secureUrl"
    :alt="alt"
    :fit="fit"
    :lazy="lazy"
    :class="imageClass"
    :style="imageStyle"
    v-bind="$attrs"
  >
    <template #placeholder>
      <div class="secure-image-placeholder">
        <el-icon class="loading-icon"><Loading /></el-icon>
        <span v-if="showLoadingText">{{ loadingText }}</span>
      </div>
    </template>
    <template #error>
      <div class="secure-image-error">
        <el-icon><PictureFilled /></el-icon>
        <span>{{ error ? error.message : errorText }}</span>
      </div>
    </template>
  </el-image>
</template>

<script setup>
import { computed, watch } from 'vue'
import { Loading, PictureFilled } from '@element-plus/icons-vue'
import { useSecureImage } from '../composables/useSecureImage'

const props = defineProps({
  src: {
    type: String,
    required: true
  },
  alt: {
    type: String,
    default: '图片'
  },
  fit: {
    type: String,
    default: 'cover',
    validator: (value) => ['fill', 'contain', 'cover', 'none', 'scale-down'].includes(value)
  },
  lazy: {
    type: Boolean,
    default: true
  },
  width: {
    type: [Number, String],
    default: 'auto'
  },
  height: {
    type: [Number, String],
    default: 'auto'
  },
  borderRadius: {
    type: [Number, String],
    default: 0
  },
  loadingText: {
    type: String,
    default: '加载中...'
  },
  errorText: {
    type: String,
    default: '加载失败'
  },
  showLoadingText: {
    type: Boolean,
    default: false
  }
})

const { secureUrl, loading, error, refresh } = useSecureImage(props.src)

// 监听 src 变化，重新加载
watch(() => props.src, (newSrc) => {
  if (newSrc) {
    refresh()
  }
})

const imageClass = computed(() => ['secure-image'])

const imageStyle = computed(() => ({
  width: typeof props.width === 'number' ? `${props.width}px` : props.width,
  height: typeof props.height === 'number' ? `${props.height}px` : props.height,
  borderRadius: typeof props.borderRadius === 'number' ? `${props.borderRadius}px` : props.borderRadius
}))

defineExpose({
  refresh,
  loading,
  error
})
</script>

<style scoped>
.secure-image {
  display: block;
  width: 100%;
  height: 100%;
}

.secure-image-placeholder,
.secure-image-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background-color: var(--el-fill-color-light);
  color: var(--el-text-color-secondary);
  gap: 8px;
}

.loading-icon {
  font-size: 24px;
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.secure-image-error .el-icon {
  font-size: 32px;
}

.secure-image-error span {
  font-size: 12px;
}
</style>

