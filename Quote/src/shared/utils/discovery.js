// src/utils/discovery.js
// 局域网自动发现主设备：Electron 下调用主进程网段扫描；Web 下跳过（返回 null）。
import { isElectron } from './imageSync'
import { setBackendBase } from './backendConfig'

/**
 * 自动发现主设备并写入后端地址；返回命中的基地址或 null。
 * 发现到即覆盖 localStorage 里的手动地址，后续请求走新地址。
 */
export async function discoverAndSetHost() {
  if (!isElectron) return null
  try {
    const host = await window.hhzAPI.discoverHost()
    if (host) {
      setBackendBase(host)
      return host
    }
  } catch {
    /* ignore */
  }
  return null
}
