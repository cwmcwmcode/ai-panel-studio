import { computed, reactive } from 'vue'
import {
  createRoom,
  finishRoom as finishRoomApi,
  getRoom,
  listRooms,
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
  readonly: false,
  notice: '',
  history: {
    open: false,
    loading: false,
    error: '',
    items: []
  },
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

function formatDateTime(input) {
  const date = input ? new Date(input) : null
  if (!date || Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
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
    summary: '',
    expertCount: room.expertCount || Math.max(1, personas.length - 1)
  }
  state.readonly = false
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

/* ---------------------------------------------------------------- */
/* 往期演播厅（历史回放）                                             */
/* ---------------------------------------------------------------- */
async function loadHistory() {
  state.history.loading = true
  state.history.error = ''
  try {
    const rooms = await listRooms()
    state.history.items = (rooms || [])
      .filter((room) => room.status === 'finished')
      .map((room) => ({
        id: room.id,
        topic: room.topic,
        status: room.status,
        expertCount: room.expert_count,
        finishedAt: room.finished_at,
        finishedLabel: formatDateTime(room.finished_at),
        summaryExcerpt: room.summary_excerpt || ''
      }))
  } catch (error) {
    state.history.error = error.message || '加载往期讨论失败，请确认后端已启动'
  } finally {
    state.history.loading = false
  }
}

function openHistory() {
  state.history.open = true
  loadHistory()
}

function closeHistory() {
  state.history.open = false
}

/**
 * 以只读方式载入一场已结题讨论：完整对白流 + 专家小窗 + 共识分歧 + 主持人总结词。
 */
async function enterArchivedRoom(room) {
  if (!room?.id) return
  state.history.loading = true
  state.history.error = ''
  try {
    closeStream()
    stopClock()
    state.modalOpen = false

    const detail = await getRoom(room.id)
    const { version = 0, items = [] } = detail.insights || {}

    state.room = {
      id: detail.room.id,
      topic: detail.room.topic,
      status: detail.room.status,
      summary: detail.room.summary || '',
      expertCount: detail.room.expertCount,
      finishedAt: detail.room.finishedAt
    }
    state.readonly = true
    state.elapsedSeconds = 0
    state.personas = detail.personas.map((persona) => ({
      ...persona,
      status: 'idle',
      focus: persona.focus || '关注议题的关键分歧'
    }))
    state.insights = items.map((item) => ({
      id: item.id,
      type: item.type,
      content: item.content,
      version: item.version ?? version
    }))
    state.insightVersion = version
    state.summaryCard = {
      visible: false,
      summary: '',
      consensus: [],
      divergence: [],
      suggestions: []
    }

    const archived = detail.transcripts.map((item) => ({
      ...item,
      lastToken: -1,
      streaming: false
    }))
    if (state.room.summary) {
      archived.push({
        id: 'summary',
        personaId: null,
        personaName: '主持人 · 收束陈词',
        color: '#10B981',
        isHost: true,
        speechType: 'summary',
        content: state.room.summary,
        time: formatClock(state.room.finishedAt),
        lastToken: -1,
        streaming: false
      })
    }
    transcriptMap.clear()
    state.transcripts = archived

    state.history.open = false
    setNotice(`已载入《${state.room.topic}》的完整回放`)
  } catch (error) {
    state.history.error = error.message || '载入历史讨论失败'
  } finally {
    state.history.loading = false
  }
}

/**
 * 基于当前议题克隆一场新讨论，重新生成阵容并进入实时 SSE 推演。
 */
async function replayRoom() {
  const topic = (state.room.topic || '').trim()
  if (!topic || topic === '等待发起一场圆桌讨论') {
    setNotice('当前没有可复用的议题')
    return
  }

  closeStream()
  stopClock()
  try {
    setNotice('正在基于该议题生成新阵容…')
    const created = await createRoom({
      topic,
      expertCount: state.room.expertCount || 4,
      style: 'debate'
    })
    draft = created
    state.history.open = false
    await confirmLineup()
    setNotice('已基于该议题发起实时推演')
  } catch (error) {
    setNotice(error.message || '重新推演失败，请稍后重试')
  }
}

/**
 * 查看当前房间的主持人总结词（历史回放与实时结束场景共用）。
 */
function showSummary() {
  if (!state.room.summary) {
    setNotice('本场暂无可查看的总结词')
    return
  }
  if (state.summaryCard.summary === state.room.summary) {
    state.summaryCard.visible = true
    return
  }
  state.summaryCard = {
    visible: true,
    summary: state.room.summary,
    consensus: state.insights
      .filter((item) => item.type === 'consensus')
      .map((item) => item.content),
    divergence: state.insights
      .filter((item) => item.type === 'divergence')
      .map((item) => item.content),
    suggestions: []
  }
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
    loadHistory,
    openHistory,
    closeHistory,
    enterArchivedRoom,
    replayRoom,
    showSummary,
    dispose
  }
}
