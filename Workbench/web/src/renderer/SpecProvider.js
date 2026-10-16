/**
 * SpecProvider：SpecContext 的 Vue 适配层（provide / inject）。
 *
 * 纯逻辑（默认值、格式化、列解析）在 SpecContext.js，不依赖 vue，
 * 这样它可以被 node --test 直接单测，不需要前端依赖。
 */
import { inject, provide } from 'vue';

import { createSpecContext } from './SpecContext.js';

const SPEC_CONTEXT_KEY = Symbol('qs-spec-context');

export function provideSpecContext(spec) {
  const ctx = createSpecContext(spec);
  provide(SPEC_CONTEXT_KEY, ctx);
  return ctx;
}

export function useSpecContext() {
  return inject(SPEC_CONTEXT_KEY, createSpecContext(null));
}
