import test from 'node:test';
import assert from 'node:assert/strict';

import {
  LEGACY_TOKEN_KEY,
  OFFLINE_KEY,
  TOKEN_KEY,
  USER_KEY,
  clearOfflineMode,
  clearSession,
  describeLoginError,
  hasToken,
  isOfflineMode,
  readToken,
  readUsername,
  setOfflineMode,
  writeSession,
} from '../session.js';

function fakeStorage() {
  const map = new Map();
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => map.set(key, String(value)),
    removeItem: (key) => map.delete(key),
    has: (key) => map.has(key),
  };
}

function withStorage() {
  const storage = fakeStorage();
  globalThis.localStorage = storage;
  return storage;
}

test('无 localStorage 时全部降级，不抛异常', () => {
  globalThis.localStorage = undefined;
  assert.equal(readToken(), '');
  assert.equal(hasToken(), false);
  assert.equal(readUsername(), '');
  assert.equal(isOfflineMode(), false);
  assert.doesNotThrow(() => writeSession('t', 'u'));
  assert.doesNotThrow(() => clearSession());
  assert.doesNotThrow(() => setOfflineMode());
  assert.doesNotThrow(() => clearOfflineMode());
});

test('登录写入令牌与用户名，并清掉旧键与离线标记', () => {
  const storage = withStorage();
  storage.setItem(LEGACY_TOKEN_KEY, 'old-token');
  setOfflineMode();

  writeSession('jwt-abc', 'sales01');

  assert.equal(readToken(), 'jwt-abc');
  assert.equal(storage.getItem(LEGACY_TOKEN_KEY), null);
  assert.equal(readUsername(), 'sales01');
  assert.equal(isOfflineMode(), false);
  assert.equal(hasToken(), true);
});

test('兼容旧键：只有 legacy 令牌时也算已登录', () => {
  const storage = withStorage();
  storage.setItem(LEGACY_TOKEN_KEY, 'legacy-token');
  assert.equal(readToken(), 'legacy-token');
  assert.equal(hasToken(), true);
});

test('clearSession 清空令牌与用户名', () => {
  withStorage();
  writeSession('jwt-abc', 'sales01');
  clearSession();
  assert.equal(readToken(), '');
  assert.equal(readUsername(), '');
  assert.equal(hasToken(), false);
});

test('离线模式独立于令牌：清了会话仍保持离线可用', () => {
  withStorage();
  setOfflineMode();
  clearSession();
  assert.equal(hasToken(), false);
  assert.equal(isOfflineMode(), true);
  clearOfflineMode();
  assert.equal(isOfflineMode(), false);
});

test('键名必须与 shared/api/http.js 的令牌键一致（否则登录态不生效）', () => {
  assert.equal(TOKEN_KEY, 'quote_workbench_token');
  assert.equal(LEGACY_TOKEN_KEY, 'hhz_workbench_token');
  assert.equal(USER_KEY, 'quote_sales_user');
  assert.equal(OFFLINE_KEY, 'quote_offline_use');
});

test('describeLoginError 把两类失败翻成可照做的中文', () => {
  assert.ok(describeLoginError(new Error('用户名或密码错误')).includes('用户名或密码错误'));
  assert.ok(describeLoginError(new Error('用户名或密码错误')).includes('管理员'));
  assert.ok(
    describeLoginError(new Error('无法连接后端服务，请确认后端已启动')).includes('连不上主设备')
  );
  assert.equal(describeLoginError(new Error('其它未知错误')), '其它未知错误');
  assert.equal(describeLoginError(null), '登录失败，请重试。');
});
