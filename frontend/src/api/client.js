/**
 * 后端网络请求层（REST + SSE）
 * ---------------------------------------------------------------
 * 开发环境默认走 Vite 代理（/api -> http://127.0.0.1:8000），
 * 也可通过 VITE_API_BASE_URL 指向独立域名（此时由后端 CORS 放行）。
 */

const RAW_BASE = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
const BASE_URL = `${RAW_BASE}/api`

export class ApiError extends Error {
  constructor(message, { code = 'NETWORK_ERROR', status = 0 } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options
    })
  } catch (error) {
    throw new ApiError('无法连接后端服务，请确认 FastAPI 已启动', { code: 'NETWORK_ERROR' })
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const error = payload?.error
    throw new ApiError(error?.message || `请求失败（${response.status}）`, {
      code: error?.code,
      status: response.status
    })
  }
  return payload?.data
}

/* ------------------------------------------------------------------ */
/* 字段映射：后端 snake_case -> 前端领域模型                            */
/* ------------------------------------------------------------------ */
export function mapPersona(persona) {
  return {
    id: persona.id,
    name: persona.name,
    title: persona.title,
    stance: persona.stance,
    color: persona.color_theme,
    isHost: Boolean(persona.is_host),
    status: persona.current_status || 'idle',
    focus: persona.current_focus || ''
  }
}

export function mapRoom(room) {
  return {
    id: room.id,
    topic: room.topic,
    status: room.status,
    summary: room.summary || '',
    expertCount: room.expert_count,
    createdAt: room.created_at,
    finishedAt: room.finished_at
  }
}

export function mapTranscript(transcript) {
  return {
    id: transcript.sequence_no,
    personaId: transcript.persona_id,
    personaName: transcript.persona_name || '嘉宾',
    color: transcript.color_theme || '#8B93A7',
    isHost: Boolean(transcript.is_host),
    speechType: transcript.speech_type || 'speech',
    content: transcript.content || '',
    time: transcript.created_at ? transcript.created_at.slice(11, 19) : '--:--:--'
  }
}

/* ------------------------------------------------------------------ */
/* REST                                                               */
/* ------------------------------------------------------------------ */
export async function listRooms(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  const suffix = query.toString() ? `?${query.toString()}` : ''
  return request(`/rooms${suffix}`)
}

export async function createRoom({ topic, expertCount = 4, style = 'debate' }) {
  const data = await request('/rooms', {
    method: 'POST',
    body: JSON.stringify({ topic, expert_count: expertCount, style })
  })
  return {
    room: mapRoom(data.room),
    personas: (data.personas || []).map(mapPersona)
  }
}

export async function getRoom(roomId) {
  const data = await request(`/rooms/${roomId}`)
  return {
    room: mapRoom(data.room),
    personas: (data.personas || []).map(mapPersona),
    transcripts: (data.transcripts || []).map(mapTranscript),
    insights: data.insights,
    progress: data.progress
  }
}

export async function startRoom(roomId) {
  return request(`/rooms/${roomId}/start`, { method: 'POST' })
}

export async function finishRoom(roomId) {
  return request(`/rooms/${roomId}/finish`, { method: 'POST' })
}

/* ------------------------------------------------------------------ */
/* SSE 流式读取                                                        */
/* ------------------------------------------------------------------ */
function parseFrame(raw) {
  const lines = raw.split('\n')
  let event = 'message'
  let id = null
  const dataLines = []

  for (const line of lines) {
    if (!line || line.startsWith(':')) continue
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('id:')) id = line.slice(3).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }

  if (dataLines.length === 0) return null
  try {
    return { event, id, data: JSON.parse(dataLines.join('\n')) }
  } catch {
    return null
  }
}

/**
 * 消费房间事件流。
 * @param {number} roomId
 * @param {{ onEvent: (event: string, data: object, id: string|null) => void }} handlers
 * @param {AbortSignal} signal
 */
export async function streamRoomEvents(roomId, { onEvent }, signal) {
  const response = await fetch(`${BASE_URL}/rooms/${roomId}/events`, {
    headers: { Accept: 'text/event-stream' },
    signal
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new ApiError(payload?.error?.message || `事件流建立失败（${response.status}）`, {
      code: payload?.error?.code,
      status: response.status
    })
  }
  if (!response.body) {
    throw new ApiError('当前浏览器不支持流式响应读取', { code: 'STREAM_UNSUPPORTED' })
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      buffer = buffer.replace(/\r\n/g, '\n')

      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const raw = buffer.slice(0, boundary)
        buffer = buffer.slice(boundary + 2)
        const frame = parseFrame(raw)
        if (frame) onEvent(frame.event, frame.data, frame.id)
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally {
    reader.releaseLock()
  }
}
