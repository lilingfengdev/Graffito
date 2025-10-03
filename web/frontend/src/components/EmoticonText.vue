<template>
  <span class="emoticon-text" v-html="parsedContent"></span>
</template>

<script setup>
import { computed } from 'vue'
import { parseEmoticons } from '../utils/format'

const props = defineProps({
  content: {
    type: String,
    default: ''
  }
})

// 解析表情包并返回带有 HTML 的内容
const parsedContent = computed(() => {
  return parseEmoticons(props.content)
})
</script>

<style scoped>
.emoticon-text {
  display: inline;
}

/* 表情包样式 */
.emoticon-text :deep(.qzone-emoticon) {
  display: inline-block;
  vertical-align: middle;
  width: 24px;
  height: 24px;
  margin: 0 2px;
  object-fit: contain;
  image-rendering: -webkit-optimize-contrast;
  image-rendering: crisp-edges;
  border: none;
  background: transparent;
  outline: none;
}

/* 移动端适配 */
@media (max-width: 768px) {
  .emoticon-text :deep(.qzone-emoticon) {
    width: 20px;
    height: 20px;
    margin: 0 1px;
  }
}

@media (max-width: 480px) {
  .emoticon-text :deep(.qzone-emoticon) {
    width: 18px;
    height: 18px;
  }
}
</style>

