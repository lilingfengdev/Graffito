<template>
  <div 
    class="secure-avatar"
    :style="avatarStyle"
  >
    <img
      v-if="src"
      :src="src"
      :alt="alt"
      referrerpolicy="no-referrer"
      @error="handleError"
      @load="handleLoad"
      class="avatar-image"
    />
    <div v-else class="avatar-placeholder">
      {{ placeholder }}
    </div>
    <div v-if="!imageLoaded && !imageError" class="avatar-placeholder">
      {{ placeholder }}
    </div>
    <div v-if="imageError" class="avatar-placeholder">
      {{ placeholder }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  src: {
    type: String,
    default: ''
  },
  size: {
    type: [Number, String],
    default: 40
  },
  alt: {
    type: String,
    default: '头像'
  },
  placeholder: {
    type: String,
    default: '?'
  },
  shape: {
    type: String,
    default: 'circle',
    validator: (value) => ['circle', 'square'].includes(value)
  },
  backgroundColor: {
    type: String,
    default: '#6366f1'
  }
})

const imageLoaded = ref(false)
const imageError = ref(false)

const avatarStyle = computed(() => {
  const size = typeof props.size === 'number' ? `${props.size}px` : props.size
  return {
    width: size,
    height: size,
    borderRadius: props.shape === 'circle' ? '50%' : '4px',
    backgroundColor: props.backgroundColor
  }
})

const handleLoad = () => {
  imageLoaded.value = true
  imageError.value = false
}

const handleError = () => {
  imageLoaded.value = false
  imageError.value = true
}
</script>

<style scoped>
.secure-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  flex-shrink: 0;
  font-size: 14px;
  color: #fff;
  font-weight: 500;
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.avatar-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-weight: 500;
  user-select: none;
}
</style>


