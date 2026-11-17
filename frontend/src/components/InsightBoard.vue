<script setup>
import { computed } from 'vue'

const props = defineProps({
  insights: { type: Array, default: () => [] },
  version: { type: Number, default: 1 }
})

const consensus = computed(() => props.insights.filter((item) => item.type === 'consensus'))
const divergence = computed(() => props.insights.filter((item) => item.type === 'divergence'))

const LANES = [
  {
    key: 'consensus',
    title: '共识',
    dot: 'bg-emerald-400',
    badge: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    card: 'border-emerald-500/25 bg-emerald-500/[0.07] hover:border-emerald-400/50',
    text: 'text-emerald-50'
  },
  {
    key: 'divergence',
    title: '分歧',
    dot: 'bg-orange-400',
    badge: 'border-orange-500/30 bg-orange-500/10 text-orange-300',
    card: 'border-orange-500/25 bg-orange-500/[0.07] hover:border-orange-400/50',
    text: 'text-orange-50'
  }
]
</script>

<template>
  <aside
    class="col-span-3 flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur"
  >
    <div class="flex shrink-0 items-center gap-2 border-b border-slate-800 px-4 py-3">
      <h2 class="text-[13px] font-semibold tracking-wide text-slate-200">共识与分歧</h2>
      <span class="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
        v{{ version }}
      </span>
      <span class="ml-auto text-[10px] text-slate-600">实时演化</span>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-2 gap-3 px-3 py-3">
      <div v-for="lane in LANES" :key="lane.key" class="flex min-h-0 flex-col">
        <div class="mb-2 flex shrink-0 items-center gap-1.5">
          <span class="h-1.5 w-1.5 rounded-full" :class="lane.dot"></span>
          <span class="text-[11px] font-medium text-slate-300">{{ lane.title }}</span>
          <span class="ml-auto rounded border px-1.5 text-[10px] leading-4" :class="lane.badge">
            {{ lane.key === 'consensus' ? consensus.length : divergence.length }}
          </span>
        </div>

        <div class="studio-scroll min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
          <article
            v-for="item in lane.key === 'consensus' ? consensus : divergence"
            :key="item.id"
            class="animate-glow-in rounded-lg border p-2 transition"
            :class="lane.card"
          >
            <p class="text-[11px] leading-5" :class="lane.text">{{ item.content }}</p>
            <p class="mt-1 font-mono text-[9px] text-slate-500">v{{ item.version }}</p>
          </article>

          <p
            v-if="(lane.key === 'consensus' ? consensus : divergence).length === 0"
            class="pt-6 text-center text-[10px] text-slate-600"
          >
            暂无{{ lane.title }}条目
          </p>
        </div>
      </div>
    </div>
  </aside>
</template>
