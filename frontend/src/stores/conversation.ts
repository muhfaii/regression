import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ChatMessage {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content_type: 'text' | 'config' | 'result'
  payload: Record<string, unknown>
  created_at: string
}

export interface Conversation {
  id: string
  title: string
  dataset_name: string | null
  created_at: string
  updated_at: string
  messages: ChatMessage[]
}

export const useConversationStore = defineStore('conversation', () => {
  const currentId = ref<string | null>(null)
  const title = ref('')
  const datasetName = ref<string | null>(null)
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)

  function reset() {
    currentId.value = null
    title.value = ''
    datasetName.value = null
    messages.value = []
    loading.value = false
  }

  function setConversation(conv: Conversation) {
    currentId.value = conv.id
    title.value = conv.title
    datasetName.value = conv.dataset_name
    messages.value = conv.messages
  }

  function addMessage(msg: ChatMessage) {
    messages.value.push(msg)
  }

  return {
    currentId, title, datasetName, messages, loading,
    reset, setConversation, addMessage,
  }
})
