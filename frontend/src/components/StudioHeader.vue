<script setup>
import { computed } from 'vue'

const props = defineProps({
  topic: { type: String, required: true },
  status: { type: String, default: 'active' },
  elapsed: { type: String, default: '00:00' }
})

defineEmits(['open-setup', 'finish'])

const STATUS_META = {
  draft: {
    label: '未开始',
    chip: 'border-slate-600 bg-slate-700/30 text-slate-300',
    dot: 'bg-slate-400'
  },
  active: {
    label: '讨论中',
    chip: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
    dot: 'bg-emerald-400 animate-breathe'
  },
  finished: {
    label: '已总结',
    chip: 'border-sky-500/40 bg-sky-500/10 text-sky-300',
    dot: 'bg-sky-400'
  }
}

const statusMeta = computed(() => STATUS_META[props.status] ?? STATUS_META.draft)
</script>

<template>
  <header
    class="flex h-16 shrink-0 items-center gap-6 border-b border-slate-800 bg-slate-900/70 px-6 backdrop-blur"
  >
    <!-- 品牌与议题 -->
    <div class="flex min-w-0 flex-1 items-center gap-3">
      <div
        class="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-[11px] font-bold tracking-widest text-emerald-300"
      >
        AI
      </div>
      <div class="min-w-0">
        <p class="text-[10px] font-medium uppercase tracking-[0.28em] text-slate-500">
          AI Panel Studio · 演播厅
        </p>
        <h1 class="truncate text-[15px] font-semibold text-slate-100" :title="topic">
          {{ topic }}
        </h1>
      </div>
    </div>

    <!-- 会议时长 -->
    <div class="hidden shrink-0 items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-1.5 md:flex">
      <span class="text-[10px] uppercase tracking-widest text-slate-500">On Air</span>
      <span class="font-mono text-sm tabular-nums text-slate-200">{{ elapsed }}</span>
    </div>

    <!-- 状态与操作 -->
    <div class="flex shrink-0 items-center gap-3">
      <span
        class="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium"
        :class="statusMeta.chip"
      >
        <span class="h-1.5 w-1.5 rounded-full" :class="statusMeta.dot"></span>
        {{ statusMeta.label }}
      </span>

      <button
        type="button"
        class="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white"
        @click="$emit('open-setup')"
      >
        发起新讨论
      </button>

      <button
        type="button"
        class="rounded-lg bg-emerald-500 px-3.5 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
        :disabled="status !== 'active'"
        @click="$emit('finish')"
      >
        主持人总结
      </button>
    </div>
  </header>
</template>
