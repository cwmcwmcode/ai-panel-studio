import { computed, reactive } from 'vue'

/**
 * 演播厅状态层（Mock）
 * ---------------------------------------------------------------
 * 一期前端先以内存 Mock 驱动，接口形态与 docs/API.md 的领域字段保持一致：
 * - persona: id / name / title / stance / stanceSide / color / isHost / status / focus
 * - transcript: id / personaId / personaName / color / speechType / content / time
 * - insight: id / type / content / version
 * 后续接入 SSE 时，仅需替换本文件的推送来源，组件无需改动。
 */

const HOST_COLOR = '#8B93A7'
const EXPERT_COLORS = ['#E4572E', '#2E86AB', '#7A9E3F', '#B565A7', '#F2A541', '#38BDF8']

const HOST_TEMPLATE = {
  id: 100,
  name: '沈知远',
  title: '圆桌主持人 · 科技观察者',
  stance: '中立引导，负责串联观点与收束结论',
  stanceSide: 'neutral',
  color: HOST_COLOR,
  isHost: true,
  focus: '串联观点并收束结论'
}

const EXPERT_POOL = [
  {
    name: '林岸',
    title: '平台架构师',
    stance: '支持立即拆分，组织规模已到临界点',
    stanceSide: 'pro',
    focus: '评估组织边界是否达标'
  },
  {
    name: '周砚',
    title: '单体系统维护者',
    stance: '反对过早拆分，分布式复杂度代价过高',
    stanceSide: 'con',
    focus: '警惕分布式复杂度成本'
  },
  {
    name: '许听',
    title: '组织效能顾问',
    stance: '先改组织结构，再谈架构拆分',
    stanceSide: 'pro',
    focus: '先改组织再谈架构'
  },
  {
    name: '顾临',
    title: '成本与稳定性工程师',
    stance: '关注运维负担与故障面的扩大',
    stanceSide: 'neutral',
    focus: '关注运维负担与故障面'
  },
  {
    name: '闻舒',
    title: '交付效率研究员',
    stance: '拆分收益取决于团队自治程度',
    stanceSide: 'pro',
    focus: '衡量团队自治成熟度'
  }
]

const MOCK_DIALOGUE = [
  { personaId: 1, speechType: 'speech', content: '拆分的门槛不是技术，而是团队边界是否清晰。' },
  { personaId: 2, speechType: 'counter', content: '边界不清晰就先拆，只会把耦合搬到服务之间。' },
  { personaId: 3, speechType: 'speech', content: '我同意边界优先，但可以先挑一条业务线试点。' },
  { personaId: 4, speechType: 'counter', content: '试点听起来稳妥，实际是在用时间换确定性。' },
  { personaId: 1, speechType: 'speech', content: '如果不拆，交付效率会继续被单体的发布节奏拖住。' },
  { personaId: 2, speechType: 'counter', content: '发布节奏的问题，未必要靠拆分来解决。' }
]

const CONSENSUS_POOL = [
  '拆分需以团队边界清晰为前提',
  '小范围试点优于一次性全量重构',
  '组织能力应先行于架构演进'
]

const DIVERGENCE_POOL = [
  '当前规模下是否应立即动手',
  '预算与人力由谁承担',
  '先改组织还是先拆服务'
]

const state = reactive({
  room: {
    topic: '我们该不该把单体服务拆成微服务？',
    status: 'active',
    summary: ''
  },
  elapsedSeconds: 95,
  personas: [],
  transcripts: [],
  insights: [],
  insightVersion: 3,
  modalOpen: false
})

let transcriptSeq = 1
let insightSeq = 1
let speechCursor = 0
let insightCursor = 0
let clockTimer = null
let speechTimer = null
let thinkingTimer = null
const pendingTimeouts = new Set()

/* ---------------------------------------------------------------- */
/* 工具函数                                                          */
/* ---------------------------------------------------------------- */
function formatClock(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function buildPersona(template, index, isHost = false) {
  return {
    id: isHost ? HOST_TEMPLATE.id : index + 1,
    name: template.name,
    title: template.title,
    stance: template.stance,
    stanceSide: template.stanceSide,
    color: isHost ? HOST_COLOR : EXPERT_COLORS[index % EXPERT_COLORS.length],
    isHost,
    status: 'idle',
    focus: template.focus
  }
}

export function buildLineup(expertCount = 4) {
  const experts = EXPERT_POOL.slice(0, Math.min(expertCount, EXPERT_POOL.length)).map(
    (template, index) => buildPersona(template, index)
  )
  return [buildPersona(HOST_TEMPLATE, 0, true), ...experts]
}

function personaById(id) {
  return state.personas.find((persona) => persona.id === id)
}

function pushTranscript(persona, content, speechType) {
  if (!persona) return
  state.transcripts.push({
    id: transcriptSeq++,
    personaId: persona.id,
    personaName: persona.name,
    color: persona.color,
    isHost: persona.isHost,
    speechType,
    content,
    time: formatClock()
  })
}

function schedule(callback, delay) {
  const timer = window.setTimeout(() => {
    pendingTimeouts.delete(timer)
    callback()
  }, delay)
  pendingTimeouts.add(timer)
}

/* ---------------------------------------------------------------- */
/* Mock 数据播种                                                      */
/* ---------------------------------------------------------------- */
function seedTranscripts() {
  const now = Date.now()
  const seeds = [
    { personaId: 100, speechType: 'intro', content: '欢迎来到演播厅。本场议题是「我们该不该把单体服务拆成微服务？」', offset: 96 },
    { personaId: 1, speechType: 'speech', content: '拆分的门槛不是技术，而是团队边界是否清晰。', offset: 74 },
    { personaId: 2, speechType: 'counter', content: '边界不清晰就先拆，只会把耦合搬到服务之间。', offset: 58 },
    { personaId: 3, speechType: 'speech', content: '我同意边界优先，但可以先挑一条业务线试点。', offset: 41 },
    { personaId: 4, speechType: 'counter', content: '试点听起来稳妥，实际是在用时间换确定性。', offset: 23 },
    { personaId: 1, speechType: 'speech', content: '如果不拆，交付效率会继续被单体的发布节奏拖住。', offset: 6 }
  ]

  state.transcripts = seeds.map((seed) => {
    const persona = personaById(seed.personaId)
    return {
      id: transcriptSeq++,
      personaId: seed.personaId,
      personaName: persona ? persona.name : '未知',
      color: persona ? persona.color : HOST_COLOR,
      isHost: persona ? persona.isHost : false,
      speechType: seed.speechType,
      content: seed.content,
      time: formatClock(new Date(now - seed.offset * 1000))
    }
  })
}

function seedInsights() {
  state.insights = [
    { id: insightSeq++, type: 'consensus', content: '拆分需以团队边界清晰为前提', version: 1 },
    { id: insightSeq++, type: 'consensus', content: '小范围试点优于一次性全量重构', version: 2 },
    { id: insightSeq++, type: 'divergence', content: '当前规模下是否应立即动手', version: 2 },
    { id: insightSeq++, type: 'divergence', content: '预算与人力由谁承担', version: 3 }
  ]
}

function pushInsightUpdate() {
  const type = insightCursor % 2 === 0 ? 'consensus' : 'divergence'
  const pool = type === 'consensus' ? CONSENSUS_POOL : DIVERGENCE_POOL
  const content = pool[Math.floor(insightCursor / 2) % pool.length]
  insightCursor += 1

  if (state.insights.some((item) => item.content === content)) return

  state.insightVersion += 1
  state.insights.push({ id: insightSeq++, type, content, version: state.insightVersion })
}

/* ---------------------------------------------------------------- */
/* 模拟讨论推进                                                       */
/* ---------------------------------------------------------------- */
function pushNextSpeech() {
  if (state.room.status !== 'active' || state.personas.length === 0) return

  const script = MOCK_DIALOGUE[speechCursor % MOCK_DIALOGUE.length]
  speechCursor += 1

  const speaker = personaById(script.personaId)
  if (!speaker) return

  state.personas.forEach((persona) => {
    if (persona.status === 'speaking') persona.status = 'idle'
  })

  speaker.status = 'speaking'
  pushTranscript(speaker, script.content, script.speechType)

  schedule(() => {
    if (speaker.status === 'speaking') speaker.status = 'idle'
  }, 3200)

  if (speechCursor % 3 === 0) pushInsightUpdate()
}

function flashThinking() {
  if (state.room.status !== 'active') return

  const candidates = state.personas.filter(
    (persona) => !persona.isHost && persona.status === 'idle'
  )
  if (candidates.length === 0) return

  const target = candidates[Math.floor(Math.random() * candidates.length)]
  target.status = 'thinking'

  schedule(() => {
    if (target.status === 'thinking') target.status = 'idle'
  }, 2100)
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

function activateRoom(topic, lineup) {
  const trimmed = (topic || '').trim()
  if (!trimmed || !lineup || lineup.length === 0) return

  state.room.topic = trimmed
  state.room.status = 'active'
  state.room.summary = ''
  state.elapsedSeconds = 0
  state.personas = lineup.map((persona) => ({ ...persona, status: 'idle' }))
  state.transcripts = []
  state.insights = []
  state.insightVersion = 1
  state.modalOpen = false
  speechCursor = 0
  insightCursor = 0

  const host = state.personas.find((persona) => persona.isHost)
  pushTranscript(
    host,
    `欢迎来到演播厅。本场议题是「${trimmed}」，请各位用一两句话亮明立场。`,
    'intro'
  )
  pushInsightUpdate()
  pushInsightUpdate()

  startSimulation()
}

function finishRoom() {
  if (state.room.status !== 'active') return

  state.room.status = 'finished'
  state.personas.forEach((persona) => {
    persona.status = 'idle'
  })

  const host = state.personas.find((persona) => persona.isHost)
  pushTranscript(
    host,
    '本场收束：共识是拆分需以团队边界清晰为前提，分歧集中在动手时机，建议先用一条业务线试点验证。',
    'summary'
  )
  stopSimulation()
}

function startSimulation() {
  stopSimulation()

  clockTimer = window.setInterval(() => {
    if (state.room.status === 'active') state.elapsedSeconds += 1
  }, 1000)
  speechTimer = window.setInterval(pushNextSpeech, 4200)
  thinkingTimer = window.setInterval(flashThinking, 3100)
}

function stopSimulation() {
  if (clockTimer) window.clearInterval(clockTimer)
  if (speechTimer) window.clearInterval(speechTimer)
  if (thinkingTimer) window.clearInterval(thinkingTimer)
  clockTimer = null
  speechTimer = null
  thinkingTimer = null

  pendingTimeouts.forEach((timer) => window.clearTimeout(timer))
  pendingTimeouts.clear()
}

/* ---------------------------------------------------------------- */
/* 初始 Mock：一位专家正在发言                                        */
/* ---------------------------------------------------------------- */
state.personas = buildLineup(4)
seedTranscripts()
seedInsights()
const openingSpeaker = personaById(1)
if (openingSpeaker) openingSpeaker.status = 'speaking'

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
    buildLineup,
    activateRoom,
    finishRoom,
    startSimulation,
    stopSimulation
  }
}
