<script setup>
import { computed } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  topic: { type: String, default: '' },
  summary: { type: String, default: '' },
  consensus: { type: Array, default: () => [] },
  divergence: { type: Array, default: () => [] },
  suggestions: { type: Array, default: () => [] }
})

const emit = defineEmits(['close'])

const hasInsights = computed(
  () => props.consensus.length > 0 || props.divergence.length > 0
)
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-300 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-200 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        class="fixed inset-0 z-[60] flex items-center justify-center bg-slate-950/85 p-6 backdrop-blur-md"
        @click.self="emit('close')"
      >
        <div
          class="studio-scroll max-h-[88vh] w-full max-w-3xl animate-glow-in overflow-y-auto rounded-2xl border border-emerald-500/30 bg-slate-900 p-7 shadow-[0_0_60px_-20px_rgba(16,185,129,0.55)]"
        >
          <!-- 头部 -->
          <div class="flex items-start gap-4">
            <div
              class="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-[11px] font-bold tracking-widest text-emerald-300"
            >
              AI
            </div>
            <div class="min-w-0 flex-1">
              <p class="text-[10px] font-medium uppercase tracking-[0.3em] text-emerald-400/80">
                Session Closed · 本场收束
              </p>
              <h2 class="mt-1 text-xl font-semibold text-slate-50">主持人总结陈词</h2>
              <p class="mt-1 truncate text-xs text-slate-500" :title="topic">{{ topic }}</p>
            </div>
            <button
              type="button"
              class="h-8 w-8 shrink-0 rounded-lg border border-slate-700 text-slate-500 transition hover:border-slate-500 hover:text-slate-200"
              aria-label="关闭总结"
              @click="emit('close')"
            >
              ×
            </button>
          </div>

          <!-- 自然语言总结 -->
          <p
            class="mt-6 rounded-xl border border-slate-800 bg-slate-950/60 p-5 text-[14px] leading-8 text-slate-200"
          >
            {{ summary }}
          </p>

          <!-- 共识 / 分歧 / 建议 -->
          <div v-if="hasInsights || suggestions.length" class="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
            <section
              v-if="consensus.length"
              class="rounded-xl border border-emerald-500/25 bg-emerald-500/[0.07] p-4"
            >
              <h3 class="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-emerald-300">
                <span class="h-1.5 w-1.5 rounded-full bg-emerald-400"></span>
                达成的共识
              </h3>
              <ul class="mt-3 space-y-2">
                <li
                  v-for="(item, index) in consensus"
                  :key="index"
                  class="flex gap-2 text-[12px] leading-6 text-emerald-50/90"
                >
                  <span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-emerald-400/70"></span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </section>

            <section
              v-if="divergence.length"
              class="rounded-xl border border-orange-500/25 bg-orange-500/[0.07] p-4"
            >
              <h3 class="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-orange-300">
                <span class="h-1.5 w-1.5 rounded-full bg-orange-400"></span>
                保留的分歧
              </h3>
              <ul class="mt-3 space-y-2">
                <li
                  v-for="(item, index) in divergence"
                  :key="index"
                  class="flex gap-2 text-[12px] leading-6 text-orange-50/90"
                >
                  <span class="mt-2 h-1 w-1 shrink-0 rounded-full bg-orange-400/70"></span>
                  <span>{{ item }}</span>
                </li>
              </ul>
            </section>

            <section
              v-if="suggestions.length"
              class="rounded-xl border border-sky-500/25 bg-sky-500/[0.06] p-4 md:col-span-2"
            >
              <h3 class="flex items-center gap-2 text-[11px] font-semibold tracking-wide text-sky-300">
                <span class="h-1.5 w-1.5 rounded-full bg-sky-400"></span>
                可执行建议
              </h3>
              <ul class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                <li
                  v-for="(item, index) in suggestions"
                  :key="index"
                  class="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2 text-[12px] leading-6 text-slate-300"
                >
                  {{ item }}
                </li>
              </ul>
            </section>
          </div>

          <!-- 底部 -->
          <div class="mt-6 flex items-center justify-end gap-3 border-t border-slate-800 pt-4">
            <p class="mr-auto text-[11px] text-slate-500">房间已结束，可关闭本卡片或发起下一场讨论。</p>
            <button
              type="button"
              class="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400"
              @click="emit('close')"
            >
              收下结论
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
