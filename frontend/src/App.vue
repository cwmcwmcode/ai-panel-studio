<script setup>
import { onBeforeUnmount, onMounted } from 'vue'
import StudioHeader from './components/StudioHeader.vue'
import PersonaCard from './components/PersonaCard.vue'
import LiveTranscript from './components/LiveTranscript.vue'
import InsightBoard from './components/InsightBoard.vue'
import DiscussionSetupModal from './components/DiscussionSetupModal.vue'
import { useStudioStore } from './stores/studioStore'

const store = useStudioStore()

onMounted(() => {
  store.startSimulation()
})

onBeforeUnmount(() => {
  store.stopSimulation()
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
      @open-setup="store.openSetup()"
      @finish="store.finishRoom()"
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
        </div>
      </aside>

      <!-- 中：现场实况 -->
      <LiveTranscript :transcripts="store.state.transcripts" />

      <!-- 右：共识与分歧看板 -->
      <InsightBoard
        :insights="store.state.insights"
        :version="store.state.insightVersion"
      />
    </main>

    <DiscussionSetupModal :open="store.state.modalOpen" @close="store.closeSetup()" />
  </div>
</template>
