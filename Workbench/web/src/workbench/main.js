// 工作台独立入口（由后端 exe 托管在浏览器访问，hash history）。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import WorkbenchApp from './App.vue'
import router from './router'
import '../shared/assets/main.css'

createApp(WorkbenchApp).use(createPinia()).use(router).mount('#app')
