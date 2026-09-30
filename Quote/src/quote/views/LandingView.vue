<script setup>
import { onMounted } from 'vue'
import { useCatalogStore } from '../../shared/stores/catalog'
import SiteHeader from '../components/SiteHeader.vue'
import QuoteSection from '../components/QuoteSection.vue'

const catalog = useCatalogStore()

// 从工作台数据库水合产品/套餐目录（管理员后台新增的会出现在报价计算器）。
// 后端不可用时静默回退到内置静态数据；手动改价能力始终保留。
onMounted(() => {
  catalog.hydrateFromRemote()
})
</script>

<template>
  <SiteHeader />
  <main>
    <QuoteSection />
  </main>
</template>
