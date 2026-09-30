"""兼容层：网络诊断（局域网发现排障用）。"""
import ipaddress
import platform
import re
import socket
import subprocess
import sys

from fastapi import APIRouter

router = APIRouter()


def _get_interfaces() -> list[dict]:
    """收集本机所有非回环 IPv4 接口信息。"""
    interfaces = []
    
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["ipconfig"], encoding="gbk", errors="replace", timeout=5
            )
            current_name = ""
            for line in out.splitlines():
                # Adapter name line (e.g., "以太网适配器 以太网:" or "无线局域网适配器 Wi-Fi:")
                m = re.match(r"^\S.*适配器\s+(.+?)\s*[:：]", line)
                if not m:
                    m = re.match(r"^\S.*adapter\s+(.+?)\s*[:：]", line, re.IGNORECASE)
                if m:
                    current_name = m.group(1).strip()
                    continue
                # IPv4 address line
                m = re.match(
                    r"^\s+IPv4.*?[:：]\s*(\d+\.\d+\.\d+\.\d+)", line
                )
                if m:
                    ip = m.group(1)
                    try:
                        is_lan = ipaddress.ip_address(ip).is_private and ip != "127.0.0.1"
                    except ValueError:
                        is_lan = False
                    interfaces.append({"name": current_name, "ip": ip, "is_lan": is_lan})
                    continue
                # Subnet mask line
                m = re.match(
                    r"^\s+子网掩码.*?[:：]\s*(\d+\.\d+\.\d+\.\d+)", line
                )
                if not m:
                    m = re.match(
                        r"^\s+Subnet Mask.*?[:：]\s*(\d+\.\d+\.\d+\.\d+)", line, re.IGNORECASE
                    )
                if m and interfaces:
                    interfaces[-1]["netmask"] = m.group(1)
        except Exception:
            pass
    else:
        # macOS / Linux: ifconfig
        try:
            out = subprocess.check_output(
                ["ifconfig"], encoding="utf-8", errors="replace", timeout=5
            )
            current_name = ""
            for line in out.splitlines():
                m = re.match(r"^(\S+?)[:：]", line)
                if m:
                    current_name = m.group(1)
                    continue
                m = re.search(
                    r"inet\s+(\d+\.\d+\.\d+\.\d+).*?(?:netmask\s+(?:0x)?(\S+)|Mask[:：](\S+))?",
                    line
                )
                if m:
                    ip = m.group(1)
                    if ip == "127.0.0.1":
                        continue
                    raw_mask = m.group(2) or m.group(3) or ""
                    # macOS returns hex netmask like 0xffffff00
                    netmask = ""
                    if raw_mask.startswith("0x") or (len(raw_mask) == 8 and all(c in '0123456789abcdef' for c in raw_mask.lower())):
                        try:
                            n = int(raw_mask, 16) if raw_mask.startswith("0x") else int("0x" + raw_mask, 16)
                            netmask = str(ipaddress.ip_address(n))
                        except (ValueError, OverflowError):
                            netmask = raw_mask
                    else:
                        netmask = raw_mask
                    try:
                        is_lan = ipaddress.ip_address(ip).is_private
                    except ValueError:
                        is_lan = False
                    interfaces.append({"name": current_name, "ip": ip, "netmask": netmask, "is_lan": is_lan})
        except Exception:
            pass
    
    # Fallback: socket-based detection
    if not interfaces:
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip == "127.0.0.1":
                    continue
                try:
                    is_lan = ipaddress.ip_address(ip).is_private
                except ValueError:
                    is_lan = False
                interfaces.append({"name": "", "ip": ip, "netmask": "", "is_lan": is_lan})
        except socket.gaierror:
            pass
    
    # Ensure all have netmask field
    for iface in interfaces:
        iface.setdefault("netmask", "")
    
    # Deduplicate by IP
    seen = set()
    unique = []
    for iface in interfaces:
        if iface["ip"] not in seen:
            seen.add(iface["ip"])
            unique.append(iface)
    return unique


def _check_firewall() -> dict:
    """Windows 防火墙 TCP 8000 入站规则检测（非 Windows 跳过）。"""
    if sys.platform != "win32":
        return {"supported": False, "reason": "非 Windows 平台，跳过防火墙检测"}
    
    try:
        # Check if firewall is enabled for current profiles
        state_out = subprocess.check_output(
            ["netsh", "advfirewall", "show", "currentprofile", "state"],
            encoding="gbk", errors="replace", timeout=5
        )
        firewall_on = "启用" in state_out or "ON" in state_out.upper()
        
        # Check if our rule exists
        rule_out = subprocess.check_output(
            ["netsh", "advfirewall", "firewall", "show", "rule",
             "name=HHZ Data Service (8000)"],
            encoding="gbk", errors="replace", timeout=5
        )
        rule_exists = "HHZ Data Service" in rule_out and ("允许" in rule_out or "Allow" in rule_out)
        
        # Determine overall status
        if not firewall_on:
            status = "off"
            message = "防火墙已关闭（所有入站均放行）"
        elif rule_exists:
            status = "ok"
            message = "防火墙已启用，TCP 8000 入站规则已生效"
        else:
            status = "warning"
            message = "防火墙已启用，但未找到 TCP 8000 入站放行规则。客户端可能无法连接。"
        
        return {
            "supported": True,
            "firewall_on": firewall_on,
            "rule_exists": rule_exists,
            "status": status,
            "message": message
        }
    except FileNotFoundError:
        return {"supported": False, "reason": "netsh 不可用"}
    except subprocess.SubprocessError:
        return {"supported": True, "status": "error", "message": "防火墙状态检测失败"}


@router.get("/network/diagnostics")
def network_diagnostics():
    """返回网络诊断信息：接口列表、服务状态、防火墙状态。"""
    interfaces = _get_interfaces()
    firewall = _check_firewall()
    
    # Find the best LAN IP for display
    lan_ips = [i["ip"] for i in interfaces if i.get("is_lan")]
    
    return {
        "interfaces": interfaces,
        "server": {
            "host": "0.0.0.0",
            "port": 8000,
            "lan_ips": lan_ips,
            "connect_urls": [f"http://{ip}:8000" for ip in lan_ips]
        },
        "firewall": firewall,
        "platform": platform.system()
    }
