# 放行 HHZ 数据服务 TCP 8000 入站（专用+公用网络，确保局域网可达）。
# 用法（管理员 PowerShell）：powershell -ExecutionPolicy Bypass -File scripts\allow-firewall.ps1
Remove-NetFirewallRule -DisplayName "HHZ Data Service (8000)" -ErrorAction SilentlyContinue
New-NetFirewallRule -DisplayName "HHZ Data Service (8000)" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private,Public | Out-Null
Write-Host "已放行 TCP 8000（专用+公用网络）。"
