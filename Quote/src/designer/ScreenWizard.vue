<script setup>
import { computed } from 'vue';

const props = defineProps({
  step: {
    type: Number,
    required: true,
  },
  answers: {
    type: Object,
    required: true,
  },
});

const emit = defineEmits(['update-answer', 'next-step', 'prev-step']);

// 预设品牌色块选项
const PRESET_COLORS = [
  { name: '科技蓝', hex: '#0B5FA5' },
  { name: '工业青', hex: '#175C8C' },
  { name: '常春藤绿', hex: '#14532D' },
  { name: '商务深灰', hex: '#1F2937' },
  { name: '勃艮第红', hex: '#881337' },
  { name: '琥珀棕', hex: '#78350F' },
];
</script>

<template>
  <div class="max-w-xl mx-auto w-full py-8 px-4 flex flex-col gap-6">
    <div class="flex items-center justify-between text-xs text-gray-400 border-b pb-3">
      <span>问题 {{ step }} / 7</span>
      <button class="hover:text-gray-600" @click="emit('next-step')">跳过此项 →</button>
    </div>

    <!-- 屏 1: 你主要卖什么？ -->
    <div v-if="step === 1" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">你主要卖什么？</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'device_with_consumable', title: '设备 + 配套耗材', desc: '主机搭配耗材组合售卖，支持自动推荐耗材' },
            { id: 'consumable_only', title: '只有耗材 / 零配件', desc: '高频出货，关注批量录入与价格分阶' },
            { id: 'service', title: '只有服务 / 解决方案', desc: '按项目或人天计费，无需实物库存与规格' },
            { id: 'mixed', title: '各种混着卖', desc: '软硬件、耗材与服务混合出单' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.sell_mode === opt.id }"
        >
          <input
            type="radio"
            name="sell_mode"
            class="mt-1"
            :checked="answers.sell_mode === opt.id"
            @change="emit('update-answer', { key: 'sell_mode', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 屏 2: 谁会用它？ -->
    <div v-if="step === 2" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">谁会用它开单或管理？</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'sales_and_boss', title: '老板 + 销售团队', desc: '销售各做各的单，老板掌握底价并统一审批' },
            { id: 'solo', title: '只有我自己', desc: '个人开单做生意，流程最简，没有审批' },
            { id: 'finance_involved', title: '销售 + 财务 + 库管', desc: '需要出库单与严格的发票条款记录' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.roles_config === opt.id }"
        >
          <input
            type="radio"
            name="roles_config"
            class="mt-1"
            :checked="answers.roles_config === opt.id"
            @change="emit('update-answer', { key: 'roles_config', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 屏 3: 一般在哪开单？ -->
    <div v-if="step === 3" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">销售一般在哪开单？</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'on_site', title: '客户现场 / 医院科室', desc: '使用笔记本带去客户办公室，左侧挑品右侧出单' },
            { id: 'office', title: '在办公室电脑前', desc: '大屏幕多列对比，查看库存与历史底价' },
            { id: 'mobile', title: '手机端移动开单', desc: '随时随地手机直接选品发给客户' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.scene === opt.id }"
        >
          <input
            type="radio"
            name="scene"
            class="mt-1"
            :checked="answers.scene === opt.id"
            @change="emit('update-answer', { key: 'scene', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 屏 4: 价格怎么定？ -->
    <div v-if="step === 4" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">价格规则怎么定？</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'floor_price', title: '按底价卖，严禁议价', desc: '低于底价直接拦截阻断开单，保护利润' },
            { id: 'negotiable', title: '可适当打折，破价需审批', desc: '允许业务员输入折让，超权限由管理员审批' },
            { id: 'tiered', title: '按数量自动阶梯价', desc: '买越多单价越低，走量批发' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.pricing_mode === opt.id }"
        >
          <input
            type="radio"
            name="pricing_mode"
            class="mt-1"
            :checked="answers.pricing_mode === opt.id"
            @change="emit('update-answer', { key: 'pricing_mode', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 屏 5: 报价单给谁看？ -->
    <div v-if="step === 5" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">最终报价单如何交付给客户？</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'print_a4', title: '打印 A4 纸质报价单', desc: '正式盖章签字送交客户采购部' },
            { id: 'export_pdf', title: '导出高品质 PDF', desc: '通过微信或邮件发送给采购' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.output_target === opt.id }"
        >
          <input
            type="radio"
            name="output_target"
            class="mt-1"
            :checked="answers.output_target === opt.id"
            @change="emit('update-answer', { key: 'output_target', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 屏 6: 放上你的品牌 -->
    <div v-if="step === 6" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">选择一套主品牌色</h2>
      <p class="text-xs text-gray-500">用于按钮、高亮金额和打印页眉，自动校准对比度保证清晰。</p>
      <div class="grid grid-cols-3 gap-3">
        <button
          v-for="c in PRESET_COLORS"
          :key="c.hex"
          class="p-3 border rounded-xl flex items-center gap-2 hover:border-gray-400 transition"
          :class="{ 'ring-2 ring-blue-500 border-transparent': answers.brand_color === c.hex }"
          @click="emit('update-answer', { key: 'brand_color', value: c.hex }); emit('update-answer', { key: 'brand_color_name', value: c.name })"
        >
          <span class="w-5 h-5 rounded-full flex-shrink-0" :style="{ backgroundColor: c.hex }"></span>
          <span class="text-xs font-medium text-gray-800">{{ c.name }}</span>
        </button>
      </div>
    </div>

    <!-- 屏 7: 选一个风格 -->
    <div v-if="step === 7" class="flex flex-col gap-4">
      <h2 class="text-xl font-bold text-gray-900">选一个界面风格包</h2>
      <div class="grid grid-cols-1 gap-3">
        <label
          v-for="opt in [
            { id: 'medical-clean', title: '医疗洁净 (Medical Clean)', desc: '舒适圆角 (8px)、明快淡蓝、中等行高' },
            { id: 'industrial-dense', title: '工业紧凑 (Industrial Dense)', desc: '严谨小圆角 (4px)、斑马线、等宽数字' },
            { id: 'brand-premium', title: '品牌轻奢 (Brand Premium)', desc: '微直角 (2px)、奢华留白、典雅色系' },
          ]"
          :key="opt.id"
          class="p-4 border rounded-xl cursor-pointer hover:border-blue-500 transition flex items-start gap-3"
          :class="{ 'border-blue-600 bg-blue-50/50': answers.preset_id === opt.id }"
        >
          <input
            type="radio"
            name="preset_id"
            class="mt-1"
            :checked="answers.preset_id === opt.id"
            @change="emit('update-answer', { key: 'preset_id', value: opt.id })"
          />
          <div>
            <div class="text-sm font-bold text-gray-900">{{ opt.title }}</div>
            <div class="text-xs text-gray-500 mt-0.5">{{ opt.desc }}</div>
          </div>
        </label>
      </div>
    </div>

    <!-- 底部翻页栏 -->
    <div class="flex items-center justify-between pt-4 border-t">
      <button
        class="text-xs text-gray-500 hover:text-gray-800"
        @click="emit('prev-step')"
      >
        ← 上一步
      </button>
      <button
        class="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold"
        @click="emit('next-step')"
      >
        {{ step === 7 ? '查看人话摘要确认 →' : '下一步 →' }}
      </button>
    </div>
  </div>
</template>
