<script setup>
import { computed } from 'vue'
import { useStudioStore } from '../stores/studioStore'

defineProps({
  open: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const store = useStudioStore()
const history = computed(() => store.state.history)
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex justify-end bg-slate-950/75 backdrop-blur-sm"
        @click.self="emit('close')"
      >
        <aside
          class="flex h-full w-full max-w-xl flex-col border-l border-slate-800 bg-slate-950/95 shadow-2xl"
        >
          <!-- 抽屉头部 -->
          <div class="flex shrink-0 items-start gap-4 border-b border-slate-800 px-6 py-5">
            <div class="min-w-0">
              <p class="text-[10px] font-medium uppercase tracking-[0.3em] text-emerald-400/80">
                Archive · 往期演播厅
              </p>
              <h2 class="mt-1 text-lg font-semibold text-slate-100">预置深度研讨</h2>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                5 场经典圆桌已结题，点击任意卡片可回看完整对白、共识分歧与主持人总结词。
              </p>
            </div>
            <button
              type="button"
              class="ml-auto h-8 w-8 shrink-0 rounded-lg border border-slate-800 text-slate-500 transition hover:border-slate-600 hover:text-slate-200"
              aria-label="关闭往期演播厅"
              @click="emit('close')"
            >
              ×
            </button>
          </div>

          <!-- 列表 -->
          <div class="studio-scroll min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-5">
            <div
              v-if="history.loading && history.items.length === 0"
              class="pt-20 text-center text-xs text-slate-500"
            >
              正在读取往期讨论…
            </div>

            <div v-else-if="history.error" class="pt-16 text-center">
              <p class="text-xs text-rose-300">{{ history.error }}</p>
              <button
                type="button"
                class="mt-3 rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-emerald-500/60 hover:text-emerald-300"
                @click="store.loadHistory()"
              >
                重新加载
              </button>
            </div>

            <p v-else-if="history.items.length === 0" class="pt-20 text-center text-xs text-slate-500">
              暂无已结题讨论，先发起一场实时讨论吧。
            </p>

            <button
              v-for="room in history.items"
              :key="room.id"
              type="button"
              class="block w-full animate-glow-in rounded-xl border border-slate-800 bg-slate-900/70 p-4 text-left transition hover:border-emerald-500/40 hover:bg-slate-900 disabled:cursor-wait disabled:opacity-60"
              :disabled="history.loading"
              @click="store.enterArchivedRoom(room)"
            >
              <div class="flex items-center gap-2">
                <span
                  class="inline-flex items-center gap-1.5 rounded-full border border-sky-500/40 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-300"
                >
                  <span class="h-1.5 w-1.5 rounded-full bg-sky-400"></span>
                  已结题
                </span>
                <span class="ml-auto font-mono text-[11px] text-slate-500">
                  {{ room.finishedLabel }}
                </span>
              </div>

              <h3 class="mt-3 text-[14px] font-semibold leading-6 text-slate-100">
                {{ room.topic }}
              </h3>

              <div class="mt-3 flex items-center gap-3 text-[11px] text-slate-500">
                <span>{{ room.expertCount }} 位专家 · 含主持共 {{ room.expertCount + 1 }} 人</span>
                <span class="ml-auto text-emerald-300/80 transition group-hover:text-emerald-300">
                  进入回放 →
                </span>
              </div>
            </button>
          </div>

          <!-- 抽屉底部 -->
          <div class="shrink-0 border-t border-slate-800 px-6 py-4">
            <p class="text-[11px] leading-5 text-slate-600">
              回放模式为只读；在演播厅顶部点击「基于此议题重新推演」可克隆议题并发起新的实时讨论。
            </p>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>
