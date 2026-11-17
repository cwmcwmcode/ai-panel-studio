<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  transcripts: { type: Array, default: () => [] }
})

const scroller = ref(null)
const stuck = ref(true)

function scrollToLatest() {
  const el = scroller.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

function onScroll() {
  const el = scroller.value
  if (!el) return
  stuck.value = el.scrollHeight - el.scrollTop - el.clientHeight < 48
}

watch(
  // token 增量不会改变数组长度，因此监听「总字符数 + 条数」保证持续吸底
  () =>
    props.transcripts.reduce((total, item) => total + (item.content?.length || 0), 0) +
    props.transcripts.length,
  async () => {
    if (!stuck.value) return
    await nextTick()
    scrollToLatest()
  }
)

onMounted(async () => {
  await nextTick()
  scrollToLatest()
})
</script>

<template>
  <section
    class="relative col-span-6 flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur"
  >
    <!-- 面板标题 -->
    <div class="flex shrink-0 items-center gap-3 border-b border-slate-800 px-5 py-3">
      <h2 class="text-[13px] font-semibold tracking-wide text-slate-200">现场实况</h2>
      <span
        class="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300"
      >
        <span class="h-1.5 w-1.5 animate-breathe rounded-full bg-emerald-400"></span>
        LIVE
      </span>
      <span class="ml-auto font-mono text-[11px] text-slate-500">{{ transcripts.length }} 条速记</span>
    </div>

    <!-- 对白瀑布流：内部独立滚动，自动吸底 -->
    <div ref="scroller" class="studio-scroll min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4" @scroll="onScroll">
      <p v-if="transcripts.length === 0" class="pt-16 text-center text-xs text-slate-600">
        等待主持人开场…
      </p>

      <div v-for="item in transcripts" :key="item.id" class="animate-glow-in">
        <div class="mb-1.5 flex items-center gap-2 text-[11px] text-slate-500">
          <span class="h-1.5 w-1.5 rounded-full" :style="{ backgroundColor: item.color }"></span>
          <span class="font-medium text-slate-400">{{ item.personaName }}</span>
          <span
            v-if="item.isHost"
            class="rounded border border-slate-700 px-1 text-[10px] leading-4 text-slate-500"
          >
            主持
          </span>
          <span class="ml-auto font-mono">{{ item.time }}</span>
        </div>

        <p
          class="rounded-xl border-l-2 px-3.5 py-2.5 text-[13.5px] leading-7 text-slate-200"
          :class="item.speechType === 'summary' ? 'ring-1 ring-emerald-500/30' : ''"
          :style="{
            borderColor: item.color,
            backgroundColor: `${item.color}12`
          }"
        >
          {{ item.content }}
        </p>
      </div>
    </div>

    <!-- 上滑浏览时提供回到底部 -->
    <button
      v-if="!stuck"
      type="button"
      class="absolute bottom-4 right-5 rounded-full border border-slate-700 bg-slate-900/90 px-3 py-1.5 text-[11px] text-slate-300 shadow-lg backdrop-blur transition hover:border-emerald-500/50 hover:text-emerald-300"
      @click="scrollToLatest(); stuck = true"
    >
      回到最新 ↓
    </button>
  </section>
</template>
