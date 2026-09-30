// electron/preload.cjs
// 在渲染进程与主进程之间安全桥接（contextIsolation + sandbox 下渲染进程无 Node 能力）。
// 仅暴露图片缓存同步所需的极简 API，不暴露任何 Node/Electron 内部能力。
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('hhzAPI', {
  isElectron: true,
  /** 从后端同步产品图片到本地缓存，返回 { ok, total, downloaded, skipped, failed, files } */
  syncImages: (backendBase) => ipcRenderer.invoke('hhz:image-sync', backendBase),
  /** 按相对路径返回本地缓存可访问 URL（app-img://cache/...），本地不存在返回 '' */
  imagePath: (rel) => ipcRenderer.invoke('hhz:image-resolve', rel),
  /** 局域网自动发现主设备，返回基地址（http://ip:8000）或 null */
  discoverHost: () => ipcRenderer.invoke('hhz:discover-host'),
  /** 目录缓存（/api/sync 结果）读 / 写，用于离线兜底 */
  readCatalogCache: () => ipcRenderer.invoke('hhz:catalog-cache-read'),
  writeCatalogCache: (payload) => ipcRenderer.invoke('hhz:catalog-cache-write', payload)
})
