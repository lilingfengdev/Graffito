<template>
  <div class="xw-upload">
    <el-upload
      v-bind="uploadProps"
      :file-list="fileList"
      :on-preview="handlePreview"
      :on-remove="handleRemove"
      :on-success="handleSuccess"
      :on-error="handleError"
      :on-progress="handleProgress"
      :before-upload="handleBeforeUpload"
      :class="uploadClasses"
    >
      <template v-if="listType === 'picture-card'">
        <el-icon class="upload-icon"><Plus /></el-icon>
      </template>
      <template v-else>
        <el-button :type="buttonType" :size="buttonSize">
          <el-icon><Upload /></el-icon>
          {{ buttonText }}
        </el-button>
      </template>
      
      <template #tip v-if="showTip">
        <div class="el-upload__tip">
          <slot name="tip">
            {{ tip || `支持上传 ${acceptText}，单文件不超过 ${formatBytes(maxSize)}` }}
          </slot>
        </div>
      </template>
    </el-upload>
    
    <!-- 预览对话框 -->
    <el-dialog
      v-model="previewVisible"
      title="预览"
      width="60%"
      :close-on-click-modal="true"
    >
      <img v-if="previewUrl" :src="previewUrl" style="width: 100%" />
      <video v-else-if="previewType === 'video'" :src="previewUrl" controls style="width: 100%" />
      <div v-else class="preview-unsupported">
        <el-icon :size="48"><Document /></el-icon>
        <p>该文件类型不支持预览</p>
        <el-button type="primary" @click="downloadFile(previewUrl)">
          下载文件
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Upload, Document } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => []
  },
  action: {
    type: String,
    required: true
  },
  accept: {
    type: String,
    default: ''
  },
  maxSize: {
    type: Number,
    default: 10 * 1024 * 1024 // 10MB
  },
  maxCount: {
    type: Number,
    default: 10
  },
  listType: {
    type: String,
    default: 'text', // text / picture / picture-card
    validator: (value) => ['text', 'picture', 'picture-card'].includes(value)
  },
  multiple: {
    type: Boolean,
    default: false
  },
  buttonText: {
    type: String,
    default: '点击上传'
  },
  buttonType: {
    type: String,
    default: 'primary'
  },
  buttonSize: {
    type: String,
    default: 'default'
  },
  showTip: {
    type: Boolean,
    default: true
  },
  tip: {
    type: String,
    default: ''
  },
  headers: {
    type: Object,
    default: () => ({})
  },
  data: {
    type: Object,
    default: () => ({})
  },
  name: {
    type: String,
    default: 'file'
  },
  withCredentials: {
    type: Boolean,
    default: false
  },
  disabled: {
    type: Boolean,
    default: false
  },
  autoUpload: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'change', 'preview', 'remove', 'success', 'error', 'progress'])

const fileList = ref(props.modelValue || [])
const previewVisible = ref(false)
const previewUrl = ref('')
const previewType = ref('')

const uploadProps = computed(() => ({
  action: props.action,
  accept: props.accept,
  multiple: props.multiple,
  listType: props.listType,
  headers: props.headers,
  data: props.data,
  name: props.name,
  withCredentials: props.withCredentials,
  disabled: props.disabled,
  limit: props.maxCount,
  autoUpload: props.autoUpload
}))

const uploadClasses = computed(() => [
  'xw-upload-wrapper',
  `xw-upload-${props.listType}`,
  {
    'xw-upload-disabled': props.disabled
  }
])

const acceptText = computed(() => {
  if (!props.accept) return '所有文件类型'
  return props.accept.replace(/\./g, '').replace(/,/g, ', ').toUpperCase()
})

const formatBytes = (bytes) => {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

const handleBeforeUpload = (file) => {
  // 检查文件大小
  if (file.size > props.maxSize) {
    ElMessage.error(`文件大小不能超过 ${formatBytes(props.maxSize)}`)
    return false
  }
  
  // 检查文件类型
  if (props.accept) {
    const acceptTypes = props.accept.split(',').map(t => t.trim())
    const fileExt = '.' + file.name.split('.').pop().toLowerCase()
    const fileType = file.type
    
    const isAccepted = acceptTypes.some(type => {
      if (type.startsWith('.')) {
        return fileExt === type
      }
      return fileType.match(new RegExp(type.replace('*', '.*')))
    })
    
    if (!isAccepted) {
      ElMessage.error(`只能上传 ${acceptText.value} 格式的文件`)
      return false
    }
  }
  
  return true
}

const handleSuccess = (response, file, fileList) => {
  emit('success', response, file, fileList)
  emit('update:modelValue', fileList)
  emit('change', fileList)
}

const handleError = (error, file, fileList) => {
  ElMessage.error('上传失败: ' + (error.message || '未知错误'))
  emit('error', error, file, fileList)
}

const handleProgress = (event, file, fileList) => {
  emit('progress', event, file, fileList)
}

const handlePreview = (file) => {
  const fileType = file.type || file.raw?.type
  previewUrl.value = file.url || URL.createObjectURL(file.raw)
  
  if (fileType?.startsWith('image/')) {
    previewType.value = 'image'
  } else if (fileType?.startsWith('video/')) {
    previewType.value = 'video'
  } else {
    previewType.value = 'other'
  }
  
  previewVisible.value = true
  emit('preview', file)
}

const handleRemove = (file, fileList) => {
  emit('remove', file, fileList)
  emit('update:modelValue', fileList)
  emit('change', fileList)
}

const downloadFile = (url) => {
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  link.click()
}
</script>

<style scoped>
.xw-upload {
  width: 100%;
}

.xw-upload-wrapper {
  width: 100%;
}

.upload-icon {
  font-size: 28px;
  color: var(--xw-text-tertiary);
  transition: var(--xw-transition);
}

.xw-upload-picture-card :deep(.el-upload) {
  border: 2px dashed var(--xw-border-primary);
  border-radius: var(--xw-radius-lg);
  transition: var(--xw-transition);
}

.xw-upload-picture-card :deep(.el-upload:hover) {
  border-color: var(--xw-primary);
}

.xw-upload-picture-card :deep(.el-upload:hover) .upload-icon {
  color: var(--xw-primary);
}

.xw-upload-disabled :deep(.el-upload) {
  cursor: not-allowed;
  opacity: 0.5;
}

.preview-unsupported {
  text-align: center;
  padding: var(--xw-space-10);
}

.preview-unsupported p {
  margin: var(--xw-space-4) 0;
  color: var(--xw-text-secondary);
}

:deep(.el-upload__tip) {
  font-size: var(--xw-text-sm);
  color: var(--xw-text-tertiary);
  margin-top: var(--xw-space-2);
}
</style>
