<script setup>
import { onBeforeUnmount } from 'vue'
import StudioHeader from './components/StudioHeader.vue'
import PersonaCard from './components/PersonaCard.vue'
import LiveTranscript from './components/LiveTranscript.vue'
import InsightBoard from './components/InsightBoard.vue'
import DiscussionSetupModal from './components/DiscussionSetupModal.vue'
import HistoryDrawer from './components/HistoryDrawer.vue'
import SummaryCard from './components/SummaryCard.vue'
import { useStudioStore } from './stores/studioStore'

const store = useStudioStore()

onBeforeUnmount(() => {
  store.dispose()
})
</script>

<template>
  <div class="studio-backdrop relative flex h-screen flex-col overflow-hidden text-slate-200">
    <!-- 演播厅氛围层（不参与布局，不产生滚动） -->
    <div class="studio-grid-lines pointer-events-none absolute inset-0 opacity-60"></div>
    <div
      class="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent"
    ></div>

    <StudioHeader
      :topic="store.state.room.topic"
      :status="store.state.room.status"
      :elapsed="store.elapsedLabel.value"
      :readonly="store.state.readonly"
      @open-setup="store.openSetup()"
      @finish="store.finishRoom()"
      @open-history="store.openHistory()"
      @replay="store.replayRoom()"
      @show-summary="store.showSummary()"
    />

    <!-- 三栏工作台：25% / 50% / 25%，各面板内部独立滚动 -->
    <main class="relative z-10 grid min-h-0 flex-1 grid-cols-12 gap-4 p-4">
      <!-- 左：专家阵容席 -->
      <aside
        class="col-span-3 flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/80 backdrop-blur"
      >
        <div class="flex shrink-0 items-center gap-2 border-b border-slate-800 px-4 py-3">
          <h2 class="text-[13px] font-semibold tracking-wide text-slate-200">专家阵容席</h2>
          <span class="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
            {{ store.state.personas.length }}
          </span>
          <span class="ml-auto text-[10px] text-slate-600">1 主持 + N 专家</span>
        </div>

        <div class="studio-scroll min-h-0 flex-1 space-y-2.5 overflow-y-auto px-3 py-3">
          <PersonaCard
            v-for="persona in store.state.personas"
            :key="persona.id"
            :persona="persona"
          />
          <p v-if="store.state.personas.length === 0" class="pt-16 text-center text-xs text-slate-600">
            尚无阵容，请先发起讨论
          </p>
        </div>
      </aside>

      <!-- 中：现场实况 -->
      <LiveTranscript
        :transcripts="store.state.transcripts"
        :live="!store.state.readonly"
      />

      <!-- 右：共识与分歧看板 -->
      <InsightBoard
        :insights="store.state.insights"
        :version="store.state.insightVersion"
      />
    </main>

    <!-- 操作提示 -->
    <Transition
      enter-active-class="transition duration-200"
      enter-from-class="translate-y-2 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-150"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="store.state.notice"
        class="pointer-events-none fixed bottom-6 left-1/2 z-40 -translate-x-1/2 rounded-full border border-slate-700 bg-slate-900/95 px-4 py-2 text-xs text-slate-200 shadow-xl backdrop-blur"
      >
        {{ store.state.notice }}
      </div>
    </Transition>

    <HistoryDrawer :open="store.state.history.open" @close="store.closeHistory()" />

    <DiscussionSetupModal :open="store.state.modalOpen" @close="store.closeSetup()" />

    <SummaryCard
      :visible="store.state.summaryCard.visible"
      :topic="store.state.room.topic"
      :summary="store.state.summaryCard.summary"
      :consensus="store.state.summaryCard.consensus"
      :divergence="store.state.summaryCard.divergence"
      :suggestions="store.state.summaryCard.suggestions"
      @close="store.dismissSummary()"
    />
  </div>
</template>
