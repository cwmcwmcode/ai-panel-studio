<script setup>
import { computed, ref, watch } from 'vue'
import { useStudioStore } from '../stores/studioStore'

const props = defineProps({
  open: { type: Boolean, default: false }
})

const emit = defineEmits(['close'])

const store = useStudioStore()
const topic = ref('')
const expertCount = ref(4)
const preview = ref([])
const loading = ref(false)
const error = ref('')

const expertOptions = [3, 4, 5]
const canGenerate = computed(() => topic.value.trim().length > 0)

watch(
  () => props.open,
  (open) => {
    if (open) {
      preview.value = []
      error.value = ''
    }
  }
)

watch([topic, expertCount], () => {
  preview.value = []
  error.value = ''
})

async function generatePreview() {
  if (!canGenerate.value || loading.value) return
  loading.value = true
  error.value = ''
  try {
    preview.value = await store.previewLineup(topic.value, expertCount.value)
  } catch (err) {
    error.value = err.message || '生成阵容失败，请检查后端服务'
  } finally {
    loading.value = false
  }
}

async function confirmLineup() {
  if (!preview.value.length || loading.value) return
  loading.value = true
  error.value = ''
  try {
    await store.confirmLineup()
    preview.value = []
    emit('close')
  } catch (err) {
    error.value = err.message || '启动讨论失败，请稍后重试'
  } finally {
    loading.value = false
  }
}

function close() {
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-6 backdrop-blur-sm"
      @click.self="close"
    >
      <div
        class="studio-scroll max-h-[86vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl"
      >
        <!-- 头部 -->
        <div class="flex items-start gap-4">
          <div class="min-w-0">
            <h3 class="text-lg font-semibold text-slate-100">发起新讨论</h3>
            <p class="mt-1 text-xs leading-5 text-slate-500">
              输入议题并选择专家人数，系统将生成 1 位主持人 + N 位专家的圆桌阵容。
            </p>
          </div>
          <button
            type="button"
            class="ml-auto h-7 w-7 shrink-0 rounded-lg border border-slate-800 text-slate-500 transition hover:border-slate-600 hover:text-slate-200"
            aria-label="关闭"
            @click="close"
          >
            ×
          </button>
        </div>

        <!-- 议题输入 -->
        <div class="mt-5">
          <label for="topic" class="text-[11px] font-medium uppercase tracking-widest text-slate-500">
            讨论议题
          </label>
          <textarea
            id="topic"
            v-model="topic"
            maxlength="200"
            rows="3"
            placeholder="例如：我们该不该把单体服务拆成微服务？"
            class="mt-2 w-full resize-none rounded-xl border border-slate-800 bg-slate-950/60 px-3.5 py-3 text-sm leading-6 text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-emerald-500/60"
          ></textarea>
          <div class="mt-1 flex items-center justify-between text-[11px] text-slate-600">
            <span>建议一句话点明争议焦点，便于生成立场对立的阵容</span>
            <span class="font-mono">{{ topic.length }}/200</span>
          </div>
        </div>

        <!-- 专家人数 -->
        <div class="mt-5">
          <span class="text-[11px] font-medium uppercase tracking-widest text-slate-500">专家人数</span>
          <div class="mt-2 flex items-center gap-2">
            <button
              v-for="option in expertOptions"
              :key="option"
              type="button"
              class="h-9 w-14 rounded-lg border text-sm font-semibold transition"
              :class="
                expertCount === option
                  ? 'border-emerald-500/60 bg-emerald-500/10 text-emerald-300'
                  : 'border-slate-800 bg-slate-950/50 text-slate-400 hover:border-slate-600 hover:text-slate-200'
              "
              @click="expertCount = option"
            >
              {{ option }}
            </button>
            <span class="ml-1 text-[11px] text-slate-500">默认 4 位，含主持人共 {{ expertCount + 1 }} 人</span>
          </div>
        </div>

        <!-- 阵容预览 -->
        <div v-if="preview.length" class="mt-6">
          <div class="mb-2 flex items-center justify-between">
            <span class="text-[11px] font-medium uppercase tracking-widest text-slate-500">阵容预览</span>
            <span class="text-[10px] text-slate-600">立场已构成可辩论光谱</span>
          </div>

          <div class="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <article
              v-for="persona in preview"
              :key="persona.id"
              class="animate-glow-in rounded-xl border bg-slate-950/40 p-3"
              :style="{ borderColor: `${persona.color}40` }"
            >
              <div class="flex items-center gap-2">
                <div
                  class="grid h-8 w-8 shrink-0 place-items-center rounded-lg border text-xs font-semibold"
                  :style="{
                    borderColor: `${persona.color}66`,
                    backgroundColor: `${persona.color}1f`,
                    color: persona.color
                  }"
                >
                  {{ persona.name.slice(0, 1) }}
                </div>
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5">
                    <p class="truncate text-[13px] font-semibold text-slate-100">{{ persona.name }}</p>
                    <span
                      v-if="persona.isHost"
                      class="rounded border border-slate-700 px-1 text-[10px] leading-4 text-slate-400"
                    >
                      主持
                    </span>
                  </div>
                  <p class="truncate text-[11px] text-slate-500">{{ persona.title }}</p>
                </div>
              </div>
              <p class="mt-2 line-clamp-2 text-[11px] leading-5 text-slate-400">{{ persona.stance }}</p>
            </article>
          </div>
        </div>

        <!-- 底部操作 -->
        <div class="mt-6 border-t border-slate-800 pt-4">
          <p v-if="error" class="mb-3 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-[11px] text-rose-300">
            {{ error }}
          </p>
          <div class="flex items-center justify-end gap-3">
            <span v-if="!canGenerate" class="mr-auto text-[11px] text-slate-600">请先输入讨论议题</span>
            <button
              type="button"
              class="rounded-lg border border-slate-700 px-3.5 py-2 text-xs text-slate-300 transition hover:border-slate-500 hover:text-white disabled:opacity-50"
              :disabled="loading"
              @click="close"
            >
              取消
            </button>
            <button
              v-if="!preview.length"
              type="button"
              class="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="!canGenerate || loading"
              @click="generatePreview"
            >
              {{ loading ? '正在生成阵容…' : '生成阵容' }}
            </button>
            <button
              v-else
              type="button"
              class="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-40"
              :disabled="loading"
              @click="confirmLineup"
            >
              {{ loading ? '正在进入演播厅…' : '确认阵容 · 进入演播厅' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
