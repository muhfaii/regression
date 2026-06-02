<script setup lang="ts">
import { computed } from 'vue'
import type { ChatMessage } from '../../stores/conversation'

const props = defineProps<{
  message: ChatMessage
}>()

const isUser = computed(() => props.message.role === 'user')
const bubbleClass = computed(() => isUser.value ? 'msg-bubble user' : 'msg-bubble assistant')

const displayText = computed(() => {
  const p = props.message.payload
  if (typeof p.text === 'string') return p.text
  return ''
})
</script>

<template>
  <div class="msg-row" :class="{ 'msg-row-user': isUser, 'msg-row-assistant': !isUser }">
    <div v-if="!isUser" class="msg-avatar">I</div>
    <div :class="bubbleClass">
      <!-- text content -->
      <p v-if="displayText" class="msg-text">{{ displayText }}</p>

      <!-- config content: render a slot for embedded config/guide/browse -->
      <div v-if="message.content_type === 'config'" class="msg-embedded">
        <slot name="config" :payload="message.payload" />
      </div>

      <!-- result content: render a slot for embedded results -->
      <div v-if="message.content_type === 'result'" class="msg-embedded">
        <slot name="result" :payload="message.payload" />
      </div>

      <div class="msg-time">{{ new Date(message.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }}</div>
    </div>
  </div>
</template>

<style scoped>
.msg-row {
  display: flex;
  gap: 12px;
  padding: 16px 0;
  max-width: 800px;
  margin: 0 auto;
  width: 100%;
}
.msg-row-user {
  flex-direction: row-reverse;
}
.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-primary);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.msg-row-user .msg-avatar {
  background: #6b7280;
}
.msg-bubble {
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.55;
  max-width: 85%;
}
.msg-bubble.user {
  background: var(--color-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
}
.msg-bubble.assistant {
  background: #f3f4f6;
  color: var(--color-text);
  border-bottom-left-radius: 4px;
}
.msg-text {
  font-size: 14px;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-embedded {
  margin-top: 4px;
}
.msg-time {
  font-size: 11px;
  color: var(--color-text-muted);
  margin-top: 6px;
  opacity: 0.7;
}
.msg-row-user .msg-time {
  color: rgba(255,255,255,0.65);
  text-align: right;
}
</style>
