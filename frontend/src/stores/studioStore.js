import { computed, reactive } from 'vue'
import {
  createRoom,
  finishRoom as finishRoomApi,
  startRoom as startRoomApi,
  streamRoomEvents
} from '../api/client'

/**
 * 演播厅状态层（REST + SSE）
 * ---------------------------------------------------------------
 * 所有内容来自后端：阵容由 POST /api/rooms 生成，讨论推进由
 * GET /api/rooms/{id}/events 的流式事件驱动。组件只消费领域状态，
 * 不感知传输细节。
 */

const state = reactive({
  room: {
    id: null,
    topic: '等待发起一场圆桌讨论',
    status: 'draft',
    summary: ''
  },
  elapsedSeconds: 0,
  personas: [],
  transcripts: [],
  insights: [],
  insightVersion: 0,
  modalOpen: false,
  streaming: false,
  notice: '',
  summaryCard: {
    visible: false,
    summary: '',
    consensus: [],
    divergence: [],
    suggestions: []
  }
})

/** 尚未进入演播厅的草稿房间（由“生成阵容”创建） */
let draft = null
const transcriptMap = new Map()
let abortController = null
let clockTimer = null
let noticeTimer = null

/* ---------------------------------------------------------------- */
/* 工具函数                                                          */
/* ---------------------------------------------------------------- */
function formatClock(input) {
  const date = input ? new Date(input) : new Date()
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function personaById(id) {
  return state.personas.find((persona) => persona.id === id)
}

function setNotice(message) {
  state.notice = message
  if (noticeTimer) window.clearTimeout(noticeTimer)
  noticeTimer = window.setTimeout(() => {
    state.notice = ''
    noticeTimer = null
  }, 4200)
}

function startClock() {
  stopClock()
  clockTimer = window.setInterval(() => {
    if (state.room.status === 'active') state.elapsedSeconds += 1
  }, 1000)
}

function stopClock() {
  if (clockTimer) window.clearInterval(clockTimer)
  clockTimer = null
}

/* ---------------------------------------------------------------- */
/* 事件消费                                                          */
/* ---------------------------------------------------------------- */
function ensureTranscript(sequenceNo, data) {
  const existing = transcriptMap.get(sequenceNo)
  if (existing) return existing

  const persona = personaById(data.persona_id)
  const item = {
    id: sequenceNo,
    personaId: data.persona_id,
    personaName: persona?.name || '嘉宾',
    color: persona?.color || '#8B93A7',
    isHost: Boolean(persona?.isHost),
    speechType: data.speech_type || 'speech',
    content: '',
    time: formatClock(),
    lastToken: -1,
    streaming: true
  }
  transcriptMap.set(sequenceNo, item)
  state.transcripts.push(item)
  return item
}

function handleEvent(event, data) {
  switch (event) {
    case 'token': {
      const item = ensureTranscript(data.sequence_no, data)
      if (typeof data.token_index === 'number') {
        if (data.token_index <= item.lastToken) return
        item.lastToken = data.token_index
      }
      item.content += data.delta || ''
      item.streaming = true

      const persona = personaById(data.persona_id)
      if (persona && persona.status !== 'speaking') persona.status = 'speaking'
      break
    }

    case 'status_change': {
      const persona = personaById(data.persona_id)
      if (!persona) return
      if (['idle', 'thinking', 'speaking'].includes(data.status)) {
        persona.status = data.status
      }
      if (data.current_focus) persona.focus = data.current_focus
      break
    }

    case 'insight_update': {
      if (typeof data.version === 'number' && data.version < state.insightVersion) return
      state.insightVersion = data.version ?? state.insightVersion
      state.insights = (data.items || []).map((item) => ({
        id: item.id,
        type: item.type,
        content: item.content,
        version: item.version ?? data.version
      }))
      break
    }

    case 'speech_end': {
      const item = ensureTranscript(data.sequence_no, data)
      item.content = data.content || item.content
      item.streaming = false
      item.time = formatClock(data.created_at)
      item.speechType = data.speech_type || item.speechType

      const persona = personaById(data.persona_id)
      if (persona) persona.status = 'idle'
      break
    }

    case 'summary': {
      state.room.status = 'finished'
      state.room.summary = data.summary || ''
      state.personas.forEach((persona) => {
        persona.status = 'idle'
      })
      state.summaryCard = {
        visible: true,
        summary: data.summary || '',
        consensus: data.consensus || [],
        divergence: data.divergence || [],
        suggestions: data.suggestions || []
      }
      stopClock()
      break
    }

    case 'done': {
      state.room.status = 'finished'
      stopClock()
      closeStream()
      break
    }

    default:
      // 未识别事件按契约忽略，不影响后续处理
      break
  }
}

async function connectStream(roomId) {
  closeStream()
  const controller = new AbortController()
  abortController = controller
  state.streaming = true

  try {
    await streamRoomEvents(roomId, { onEvent: handleEvent }, controller.signal)
  } catch (error) {
    if (error.name !== 'AbortError') {
      setNotice(error.message || '事件流中断，请稍后重试')
    }
  } finally {
    if (abortController === controller) {
      abortController = null
      state.streaming = false
    }
    if (state.room.status !== 'active') stopClock()
  }
}

function closeStream() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  state.streaming = false
}

/* ---------------------------------------------------------------- */
/* 对外动作                                                          */
/* ---------------------------------------------------------------- */
function openSetup() {
  state.modalOpen = true
}

function closeSetup() {
  state.modalOpen = false
}

/**
 * 调用后端生成阵容（创建 draft 房间），返回可预览的角色列表。
 */
async function previewLineup(topic, expertCount) {
  const trimmed = (topic || '').trim()
  if (!trimmed) throw new Error('请先输入讨论议题')

  const created = await createRoom({
    topic: trimmed,
    expertCount,
    style: 'debate'
  })
  draft = created
  return created.personas
}

/**
 * 启动刚生成的房间并接入事件流。
 */
async function confirmLineup() {
  if (!draft) throw new Error('请先生成阵容')

  const { room, personas } = draft
  await startRoomApi(room.id)

  state.room = {
    id: room.id,
    topic: room.topic,
    status: 'active',
    summary: ''
  }
  state.personas = personas.map((persona) => ({
    ...persona,
    status: 'idle',
    focus: persona.focus || '关注议题的关键分歧'
  }))
  state.transcripts = []
  state.insights = []
  state.insightVersion = 0
  state.elapsedSeconds = 0
  state.modalOpen = false
  state.summaryCard = {
    visible: false,
    summary: '',
    consensus: [],
    divergence: [],
    suggestions: []
  }
  transcriptMap.clear()
  draft = null

  startClock()
  connectStream(room.id)
}

async function finishRoom() {
  if (state.room.status !== 'active' || !state.room.id) return
  try {
    await finishRoomApi(state.room.id)
    setNotice('主持人正在收束全场观点…')
  } catch (error) {
    setNotice(error.message || '结束讨论失败')
  }
}

function dismissSummary() {
  state.summaryCard.visible = false
}

function dispose() {
  closeStream()
  stopClock()
  if (noticeTimer) window.clearTimeout(noticeTimer)
  noticeTimer = null
}

const elapsedLabel = computed(() => {
  const total = state.elapsedSeconds
  const minutes = String(Math.floor(total / 60)).padStart(2, '0')
  const seconds = String(total % 60).padStart(2, '0')
  return `${minutes}:${seconds}`
})

export function useStudioStore() {
  return {
    state,
    elapsedLabel,
    openSetup,
    closeSetup,
    previewLineup,
    confirmLineup,
    finishRoom,
    dismissSummary,
    dispose
  }
}
