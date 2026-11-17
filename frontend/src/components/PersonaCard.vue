<script setup>
import { computed } from 'vue'

const props = defineProps({
  persona: { type: Object, required: true }
})

const STATUS_META = {
  idle: {
    label: '待机',
    dot: 'bg-slate-600',
    text: 'text-slate-500',
    hint: '静默聆听中'
  },
  thinking: {
    label: '构思中',
    dot: 'bg-amber-400 animate-pulse',
    text: 'text-amber-300',
    hint: '正在组织观点'
  },
  speaking: {
    label: '发言中',
    dot: 'bg-emerald-400 animate-breathe',
    text: 'text-emerald-300',
    hint: '正在发言'
  }
}

const meta = computed(() => STATUS_META[props.persona.status] ?? STATUS_META.idle)

const glowStyle = computed(() => {
  const color = props.persona.color
  if (props.persona.status === 'speaking') {
    return {
      borderColor: `${color}99`,
      boxShadow: `0 0 22px -6px ${color}aa, inset 0 0 0 1px ${color}22`
    }
  }
  if (props.persona.status === 'thinking') {
    return {
      borderColor: `${color}66`,
      boxShadow: '0 0 16px -8px rgba(251, 191, 36, 0.55)'
    }
  }
  return { borderColor: '#1e293b', boxShadow: 'none' }
})
</script>

<template>
  <article
    class="relative animate-glow-in rounded-xl border bg-slate-900/80 p-3 transition-all duration-300"
    :style="glowStyle"
  >
    <div class="flex items-center gap-3">
      <!-- 头像与呼吸灯 -->
      <div
        class="relative grid h-9 w-9 shrink-0 place-items-center rounded-lg border text-[13px] font-semibold"
        :style="{
          borderColor: `${persona.color}66`,
          backgroundColor: `${persona.color}1f`,
          color: persona.color
        }"
      >
        {{ persona.name.slice(0, 1) }}
        <span
          class="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full ring-2 ring-slate-900"
          :class="meta.dot"
          :style="persona.status === 'speaking' ? { backgroundColor: persona.color } : {}"
        ></span>
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <p class="truncate text-[13px] font-semibold text-slate-100">{{ persona.name }}</p>
          <span
            v-if="persona.isHost"
            class="shrink-0 rounded border border-slate-700 px-1 text-[10px] leading-4 text-slate-400"
          >
            主持
          </span>
        </div>
        <p class="truncate text-[11px] text-slate-500">{{ persona.title }}</p>
      </div>

      <span class="shrink-0 text-[10px] font-medium" :class="meta.text">{{ meta.label }}</span>
    </div>

    <!-- 公开关注焦点：仅可对用户公开的摘要，绝不承载思维链 -->
    <p class="mt-2.5 flex items-center gap-1.5 truncate text-[11px] text-slate-400" :title="persona.focus">
      <span class="text-slate-600">关注</span>
      <span class="truncate">{{ persona.focus }}</span>
    </p>
  </article>
</template>
