# -*- coding: utf-8 -*-
"""Local League client bridge for the e-reader.

Reads the running client on this PC and serves one JSON page at /now.
Does not inject, read game memory, or change game files.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import socket
import subprocess
import sys
import webbrowser
import winreg
import ssl
import threading
import time
import urllib.error
import urllib.request
import io
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

HOST = "0.0.0.0"
PORT = 18765
BRIDGE_VER = "1.8.13"
FROZEN = getattr(sys, "frozen", False)
BUNDLE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ROOT = Path(os.environ.get("LOCALAPPDATA", ".")) / "DuiJuTuiJian" if FROZEN else Path(__file__).resolve().parent
CHAMP_CACHE = ROOT / "champions.json"

# Champion ids that commonly bring healing or shields worth grievous wounds.
HEAL_IDS = {
    8, 16, 19, 25, 36, 37, 40, 43, 44, 50, 63, 74, 79, 89, 101, 111, 114,
    117, 142, 143, 147, 154, 161, 201, 223, 233, 235, 266, 267, 350, 412,
    420, 517, 526, 711, 902,
}
ENCHANTER_IDS = {16, 37, 40, 43, 44, 117, 147, 267, 350, 412, 526, 902}

ACTIVE = {"ChampSelect", "GameStart", "InProgress"}
CLEAR = {"None", "Lobby", "Matchmaking", "EndOfGame", "PreEndOfGame", "WaitingForStats"}

CHAMP_PLANS = {
    157: {
        "items": [
            "毁坏仪式", "金铲铲", "暴食胫甲", "死亡之舞", "振奋盔甲", "育恩塔尔荒野箭", "轻灵之靴", "无穷饥渴", "无尽之刃", "幻影之舞", "狂战士胫甲", "破败王者之刃", "千变者贾修", "智慧末刃", "多米尼克领主的致意",
        ],
        "hex": [
            "弹跳蜜蜂", "鼓声暴起 低音轰鸣", "秘术冲拳", "魔法转物理", "将他们放倒倒倒", "狂热者", "会心防御", "男爵之手", "逃跑计划", "屹立不倒", "扇巴掌", "泰坦的坚决",
        ],
        "winrate": "58.4%",
        "pickrate": "11.5%",
        "tier": "T1",
    },
    114: {
        "items": [
            "终极九头蛇", "金铲铲", "无穷饥渴", "暴食胫甲", "死亡之舞", "魔切", "魔宗", "夺萃之镰", "贪欲九头蛇", "三相之力", "朔极之矛", "狂妄",
        ],
        "hex": [
            "秘术冲拳", "弹跳蜜蜂", "鼓声暴起 低音轰鸣", "终极九头蛇", "科学狂人", "男爵之手", "命运之武器", "大力", "魔法转物理", "回归基本功", "将他们放倒倒倒", "逃跑计划",
        ],
        "winrate": "55.7%",
        "pickrate": "7.0%",
        "tier": "T1",
    },
    4: {
        "items": [
            "暴食胫甲", "黯炎火炬", "金铲铲", "卢登的回声", "沃格勒特的巫师帽", "视界专注", "毁坏仪式", "明朗之靴", "灭世者的死亡之帽", "影焰", "巫妖之祸", "虚空之杖", "兰德里的折磨", "风暴狂涌", "中娅沙漏",
        ],
        "hex": [
            "回响施放", "拯救", "反冲", "回归基本功", "家园卫士", "科学狂人", "超强大脑", "小蜜蜂！！！", "沃格勒特的巫师帽", "巨人杀手", "术士果汁盒", "有始有终",
        ],
        "winrate": "56.4%",
        "pickrate": "12.2%",
        "tier": "T1",
    },
    10: {
        "items": [
            "金铲铲", "灭世者的死亡之帽", "沃格勒特的巫师帽", "虚空之杖", "影焰", "黄昏与黎明", "暴食胫甲", "斯塔缇克电刃", "纳什之牙", "裂隙制造者", "鬼索的狂暴之刃", "破败王者之刃", "界弓",
        ],
        "hex": [
            "虚幻武器", "鼓声暴起 低音轰鸣", "沃格勒特的巫师帽", "物法皆修", "狂热者", "神射法师", "海牛阿福的勇士", "男爵之手", "小蜜蜂！！！", "秘术冲拳", "物理转魔法", "王冠之重",
        ],
        "winrate": "55.4%",
        "pickrate": "6.4%",
        "tier": "T1",
    },
    103: {
        "items": [
            "沃格勒特的巫师帽", "暴食胫甲", "炽天使之拥", "毁坏仪式", "黯炎火炬", "巫妖之祸", "金铲铲", "星界驱驰", "灭世者的死亡之帽", "影焰", "风暴狂涌", "虚空之杖", "法师之靴", "中娅沙漏",
        ],
        "hex": [
            "男爵之手", "沃格勒特的巫师帽", "无限循环往复", "尤里卡", "巨人杀手", "科学狂人", "拯救", "唯快不破", "蓝色屏障", "有始有终", "回归基本功", "旋转至胜",
        ],
        "winrate": "52.1%",
        "pickrate": "6.6%",
        "tier": "T2",
    },
    238: {
        "items": [
            "无穷饥渴", "终极九头蛇", "死亡之舞", "金铲铲", "幽梦之灵", "暴食胫甲", "玛莫提乌斯之噬", "无尽之刃", "狂妄", "电震涡流剑", "公理圆弧", "巨蛇之牙", "收集者", "多米尼克领主的致意", "赛瑞尔达的怨恨",
        ],
        "hex": [
            "科学狂人", "将他们放倒倒倒", "命运之武器", "男爵之手", "鼓声暴起 低音轰鸣", "大地苏醒", "终极九头蛇", "快中求稳", "最终形态", "有始有终", "逃跑计划", "小丑学院",
        ],
        "winrate": "48.9%",
        "pickrate": "8.3%",
        "tier": "T3",
    },
    84: {
        "items": [
            "沃格勒特的巫师帽", "毁坏仪式", "灭世者的死亡之帽", "金铲铲", "女妖面纱", "无尽之刃", "暴食胫甲", "振奋盔甲", "风暴狂涌", "影焰", "海克斯科技枪刃", "虚空之杖", "法师之靴", "巫妖之祸", "中娅沙漏",
        ],
        "hex": [
            "男爵之手", "将他们放倒倒倒", "沃格勒特的巫师帽", "逃跑计划", "术士果汁盒", "命运之武器", "超强大脑", "拯救", "全能龙魂", "鼓声暴起 低音轰鸣", "最终形态", "科学狂人",
        ],
        "winrate": "44.2%",
        "pickrate": "3.9%",
        "tier": "T5",
    },
    875: {
        "items": [
            "虚空献祭", "金铲铲", "狂徒铠甲", "霸王血铠", "心之钢", "终极九头蛇", "日炎圣盾", "无穷饥渴", "无终恨意", "斯特拉克的挑战护手", "水银之靴", "朔极之矛", "巨型九头蛇",
        ],
        "hex": [
            "歌利亚巨人", "钢化你心", "科学狂人", "史莱姆时间", "升级：献祭", "艾卡西亚的陷落", "坦克引擎", "男爵之手", "鼓声暴起 低音轰鸣", "星界躯体", "重量级打击手", "吞噬灵魂",
        ],
        "winrate": "51.5%",
        "pickrate": "10.6%",
        "tier": "T2",
    },
}
_ctx = ssl._create_unverified_context()
_lock = threading.Lock()
_state = {
    "ok": True,
    "app": "lol_guide",
    "client": False,
    "account": "",
    "phase": "idle",
    "phaseText": "客户端未打开",
    "mode": "",
    "modeText": "",
    "queueId": 0,
    "queueName": "",
    "me": "",
    "champ": "",
    "enemies": [],
    "runes": [],
    "items": [],
    "hex": [],
    "winrate": "",
    "pickrate": "",
    "tier": "",
    "note": "",
    "ranks": [],
    "picks": [],
    "updated": 0,
}
_auth = None  # (port, token)
_summoner = None  # {id, puuid, gameName, tagLine}
_roster = None  # last seen champ select / game roster
_sticky_hex = False
_champions = {}  # id -> {name, tags}


def lan_ips() -> list:
    found = []
    seen = set()
    try:
        infos = socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
    except OSError:
        infos = []
    for info in infos:
        ip = info[4][0]
        if ip.startswith("127.") or ip.startswith("198.18.") or ip in seen:
            continue
        seen.add(ip)
        found.append(ip)
    private = [ip for ip in found if ip.startswith(("192.168.", "10.", "172."))]
    return private or found or ["127.0.0.1"]


def lan_ip() -> str:
    return lan_ips()[0]


def pair_code(ip: str) -> str:
    parts = str(ip or "").split(".")
    if len(parts) != 4 or parts[0] != "192" or parts[1] != "168":
        return ""
    try:
        a, b = int(parts[2]), int(parts[3])
    except ValueError:
        return ""
    if a < 0 or a > 255 or b < 0 or b > 255:
        return ""
    return f"{a * 256 + b:05d}"


def load_champ_cache() -> None:
    if not CHAMP_CACHE.exists():
        return
    try:
        data = json.loads(CHAMP_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    for key, value in data.items():
        try:
            cid = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict) and value.get("name"):
            _champions[cid] = {
                "name": value["name"],
                "tags": list(value.get("tags") or []),
                "id": value.get("id") or "",
            }


def save_champ_cache() -> None:
    blob = {str(cid): row for cid, row in _champions.items()}
    try:
        CHAMP_CACHE.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def fetch_ddragon() -> None:
    try:
        with urllib.request.urlopen(
            "https://ddragon.leagueoflegends.com/api/versions.json", timeout=8
        ) as resp:
            version = json.loads(resp.read().decode("utf-8"))[0]
        url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/zh_CN/champion.json"
        with urllib.request.urlopen(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, IndexError, KeyError):
        return
    changed = False
    for row in payload.get("data", {}).values():
        try:
            cid = int(row.get("key"))
        except (TypeError, ValueError):
            continue
        name = row.get("name") or ""
        tags = list(row.get("tags") or [])
        champ_id = row.get("id") or ""
        prev = _champions.get(cid)
        if not prev or prev.get("name") != name or prev.get("tags") != tags or prev.get("id") != champ_id:
            _champions[cid] = {"name": name, "tags": tags, "id": champ_id}
            changed = True
    if changed:
        save_champ_cache()


def _yaml_install_paths(path: Path):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    for line in lines:
        if "product_install_full_path" not in line or ":" not in line:
            continue
        raw = line.split(":", 1)[1].strip().strip('"').strip("'")
        if raw:
            yield Path(raw)


def _registry_install_paths():
    roots = (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, root in roots:
        try:
            key = winreg.OpenKey(hive, root)
        except OSError:
            continue
        try:
            count = winreg.QueryInfoKey(key)[0]
            for index in range(count):
                try:
                    sub = winreg.OpenKey(key, winreg.EnumKey(key, index))
                    name = str(winreg.QueryValueEx(sub, "DisplayName")[0])
                except OSError:
                    continue
                lowered = name.lower()
                if "league of legends" not in lowered and "\u82f1\u96c4\u8054\u76df" not in name:
                    continue
                for value_name in ("InstallLocation", "DisplayIcon"):
                    try:
                        raw = str(winreg.QueryValueEx(sub, value_name)[0]).strip('"')
                    except OSError:
                        continue
                    folder = Path(raw)
                    if value_name == "DisplayIcon":
                        folder = folder.parent
                    if str(folder):
                        yield folder
        finally:
            winreg.CloseKey(key)


def install_dirs():
    found = []
    seen = set()

    def add(folder):
        text = str(folder).strip()
        if not text:
            return
        key = os.path.normcase(text)
        if key in seen:
            return
        seen.add(key)
        found.append(Path(text))

    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    meta_root = program_data / "Riot Games" / "Metadata"
    if meta_root.is_dir():
        for settings in meta_root.glob("*/*.product_settings.yaml"):
            if "league" not in settings.name.lower():
                continue
            for folder in _yaml_install_paths(settings):
                add(folder)
    for folder in _registry_install_paths():
        add(folder)
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        add(Path(local) / "Riot Games" / "League of Legends")
    add(Path(r"C:\Riot Games\League of Legends"))
    tencent = "\u817e\u8baf\u6e38\u620f"
    lol = "\u82f1\u96c4\u8054\u76df"
    for letter in "CD":
        add(Path(letter + ":/") / tencent / lol)
        add(Path(letter + ":/WeGameApps"))
        add(Path(letter + ":/Program Files") / tencent / lol)
        add(Path(letter + ":/Program Files (x86)") / tencent / lol)
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(env)
        if not root:
            continue
        add(Path(root) / tencent / lol)
        base = Path(root) / "WeGameApps"
        if not base.is_dir():
            continue
        for lock in list(base.glob("*/lockfile")) + list(base.glob("*/*/lockfile")):
            add(lock.parent)
        for lock in list(base.glob("*/*/LeagueClient/lockfile")) + list(base.glob("*/LeagueClient/lockfile")):
            add(lock.parent)
    for folder in _league_process_folders():
        add(folder)
    return found


_PORT_RE = re.compile(r"--app-port(?:=|\s+)(\d+)", re.I)
_TOKEN_RE = re.compile(r"--remoting-auth-token(?:=|\s+)([^\s\"]+)", re.I)
_detect = {"hint": "", "names": []}


def _set_detect(hint: str, names=None) -> None:
    _detect["hint"] = hint
    if names is not None:
        _detect["names"] = list(names)


def _decode_out(raw: bytes) -> str:
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _run_capture(argv, timeout=8) -> str:
    try:
        raw = subprocess.check_output(
            argv,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=timeout,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""
    return _decode_out(raw)


def _auth_from_cmd(cmd: str):
    if not cmd:
        return None
    port_m = _PORT_RE.search(cmd)
    token_m = _TOKEN_RE.search(cmd)
    if not port_m or not token_m:
        return None
    port = int(port_m.group(1))
    token = token_m.group(1).strip()
    if port > 0 and token:
        return port, token
    return None


def _is_league_name(name: str) -> bool:
    lowered = (name or "").lower()
    return (
        "leagueclient" in lowered
        or "league of legends" in lowered
        or lowered.startswith("league")
        or "\u82f1\u96c4\u8054\u76df" in (name or "")
        or "riotclientux" in lowered
    )



def _k32():
    import ctypes
    return ctypes.WinDLL("kernel32", use_last_error=True)


def _image_of_pid(pid: int) -> str:
    if not pid:
        return ""
    import ctypes
    from ctypes import wintypes
    kernel32 = _k32()
    handle = kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(32768)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ""
        return buf.value
    finally:
        kernel32.CloseHandle(handle)


def _cmd_from_class60(handle) -> str:
    import ctypes
    from ctypes import wintypes
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtQueryInformationProcess.restype = ctypes.c_ulong
    size = wintypes.ULONG(0)
    ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(size))
    buflen = size.value if size.value >= 16 else 8192
    buf = ctypes.create_string_buffer(buflen)
    status = ntdll.NtQueryInformationProcess(handle, 60, buf, buflen, ctypes.byref(size))
    status &= 0xFFFFFFFF
    if status == 0xC0000004 and size.value > buflen:
        buf = ctypes.create_string_buffer(size.value)
        status = ntdll.NtQueryInformationProcess(handle, 60, buf, size.value, ctypes.byref(size))
        status &= 0xFFFFFFFF
    if status != 0:
        return ""

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", ctypes.c_ushort),
            ("MaximumLength", ctypes.c_ushort),
            ("Buffer", ctypes.c_void_p),
        ]

    us = UNICODE_STRING.from_buffer(buf)
    if us.Length and us.Buffer:
        try:
            return ctypes.wstring_at(us.Buffer, us.Length // 2)
        except Exception:
            pass
    length = int.from_bytes(buf.raw[0:2], "little")
    if length >= 2:
        blob = buf.raw[16:16 + length]
        if len(blob) == length:
            return blob.decode("utf-16-le", "replace")
    return ""


def _cmd_from_peb(handle) -> str:
    import ctypes
    from ctypes import wintypes
    if ctypes.sizeof(ctypes.c_void_p) < 8:
        return ""
    ntdll = ctypes.WinDLL("ntdll")

    class PROCESS_BASIC_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("Reserved1", ctypes.c_void_p),
            ("PebBaseAddress", ctypes.c_void_p),
            ("Reserved2", ctypes.c_void_p * 2),
            ("UniqueProcessId", ctypes.c_void_p),
            ("Reserved3", ctypes.c_void_p),
        ]

    class UNICODE_STRING(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", ctypes.c_void_p),
        ]

    kernel32 = _k32()
    pbi = PROCESS_BASIC_INFORMATION()
    status = ntdll.NtQueryInformationProcess(
        handle, 0, ctypes.byref(pbi), ctypes.sizeof(pbi), None
    )
    if status != 0 or not pbi.PebBaseAddress:
        return ""
    peb = int(pbi.PebBaseAddress)
    params = ctypes.c_void_p()
    nread = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(peb + 0x20), ctypes.byref(params), 8, ctypes.byref(nread)
    ):
        return ""
    if not params.value:
        return ""
    us = UNICODE_STRING()
    if not kernel32.ReadProcessMemory(
        handle,
        ctypes.c_void_p(int(params.value) + 0x70),
        ctypes.byref(us),
        ctypes.sizeof(us),
        ctypes.byref(nread),
    ):
        return ""
    if not us.Buffer or us.Length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(us.Length // 2 + 1)
    if not kernel32.ReadProcessMemory(
        handle, ctypes.c_void_p(int(us.Buffer)), buf, us.Length, ctypes.byref(nread)
    ):
        return ""
    return buf.value


def _cmd_of_pid(pid: int) -> str:
    if not pid:
        return ""
    kernel32 = _k32()
    text = ""
    handle = kernel32.OpenProcess(0x1000, False, int(pid))
    if handle:
        try:
            text = _cmd_from_class60(handle) or ""
        except Exception:
            text = ""
        kernel32.CloseHandle(handle)
    if "--app-port" in text.lower():
        return text
    handle = kernel32.OpenProcess(0x0410, False, int(pid))
    if handle:
        try:
            peb = _cmd_from_peb(handle) or ""
            if len(peb) > len(text):
                text = peb
        except Exception:
            pass
        kernel32.CloseHandle(handle)
    if "--app-port" in text.lower():
        return text
    raw = _run_capture(
        ["wmic", "process", "where", "processid=%d" % int(pid), "get", "CommandLine", "/value"]
    )
    for line in raw.splitlines():
        if line.lower().startswith("commandline="):
            got = line.split("=", 1)[1].strip()
            if got:
                return got
    return text


def _walk_lockfile(root: Path, max_depth: int = 5, max_dirs: int = 300):
    if not root or not root.exists():
        return None
    try:
        root = root.resolve()
    except OSError:
        return None
    if len(root.parts) < 2:
        return None
    visited = 0
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            visited += 1
            if visited > max_dirs:
                break
            try:
                depth = len(Path(dirpath).relative_to(root).parts)
            except ValueError:
                dirnames[:] = []
                continue
            if depth > max_depth:
                dirnames[:] = []
                continue
            dirnames[:] = [
                name for name in dirnames
                if name.lower() not in ("windows", "system32", "winsxs", "$recycle.bin")
            ]
            for name in filenames:
                if name.lower() == "lockfile":
                    found = _read_lock(Path(dirpath) / name)
                    if found:
                        return found
    except OSError:
        return None
    return None


def _lock_from_exe(exe: Path):
    folder = exe.parent if exe.suffix.lower() == ".exe" else exe
    found = _lock_near(folder)
    if found:
        return found
    root = folder
    for _ in range(3):
        if root.parent == root:
            break
        if root.name.lower() in ("windows", "program files", "program files (x86)"):
            break
        root = root.parent
        found = _walk_lockfile(root)
        if found:
            return found
    return None


def _toolhelp_rows() -> list:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    kernel32 = _k32()
    snap = kernel32.CreateToolhelp32Snapshot(0x2, 0)
    if snap in (-1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
        return []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    rows = []
    ok = kernel32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        name = entry.szExeFile
        if _is_league_name(name):
            pid = int(entry.th32ProcessID)
            rows.append(
                {
                    "name": name,
                    "pid": pid,
                    "exe": _image_of_pid(pid),
                    "cmd": "",
                }
            )
        ok = kernel32.Process32NextW(snap, ctypes.byref(entry))
    kernel32.CloseHandle(snap)
    return rows


def _enrich_rows(rows: list) -> list:
    snaps = _toolhelp_rows()
    by_name = {}
    for item in snaps:
        by_name.setdefault((item.get("name") or "").lower(), []).append(item)
    used = set()
    out = []
    for row in list(rows) + snaps:
        name = (row.get("name") or "").strip()
        if not _is_league_name(name):
            continue
        lowered = name.lower()
        pid = int(row.get("pid") or 0)
        if not pid:
            bucket = by_name.get(lowered) or []
            for item in bucket:
                key = item.get("pid")
                if key not in used:
                    pid = int(key)
                    if not row.get("exe"):
                        row["exe"] = item.get("exe") or ""
                    break
        if pid:
            used.add(pid)
            row["pid"] = pid
            if not row.get("exe"):
                row["exe"] = _image_of_pid(pid)
            cmd = row.get("cmd") or ""
            if "--app-port" not in cmd.lower():
                peb = _cmd_of_pid(pid)
                if peb:
                    row["cmd"] = peb
        key = (name.lower(), row.get("pid") or 0, row.get("exe") or "")
        if key in used and any(
            (r.get("name") or "").lower() == name.lower() and r.get("pid") == row.get("pid")
            for r in out
        ):
            continue
        out.append(row)
    # unique by pid/name
    uniq = []
    seen = set()
    for row in out:
        key = (row.get("pid") or 0, (row.get("name") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    return uniq


def _cim_process_rows(where: str) -> list:
    rows = []
    script = (
        "Get-CimInstance Win32_Process | Where-Object { " + where + " } | "
        "ForEach-Object { "
        "([string]$_.ProcessId + [char]9 + $_.Name + [char]9 + "
        "[string]$_.ExecutablePath + [char]9 + [string]$_.CommandLine) }"
    )
    raw = _run_capture(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        timeout=12,
    )
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        pid = 0
        try:
            pid = int(parts[0].strip())
        except ValueError:
            continue
        rows.append(
            {
                "pid": pid,
                "name": parts[1].strip(),
                "exe": parts[2].strip().strip('"') if len(parts) > 2 else "",
                "cmd": "\t".join(parts[3:]).strip() if len(parts) > 3 else "",
            }
        )
    return _enrich_rows(rows)


def _process_rows() -> list:
    rows = _enrich_rows(_toolhelp_rows())
    if rows:
        return rows
    return _cim_process_rows("$_.Name -match 'LeagueClient'")


def _league_process_folders() -> list:
    found = []
    seen = set()
    for row in _process_rows():
        exe = Path(row.get("exe") or "")
        if exe.suffix.lower() == ".exe":
            key = os.path.normcase(str(exe.parent))
            if key not in seen:
                seen.add(key)
                found.append(exe.parent)
        cmd = row.get("cmd") or ""
        for chunk in cmd.replace('"', "").split():
            if chunk.lower().endswith(".exe"):
                folder = Path(chunk).parent
                key = os.path.normcase(str(folder))
                if key not in seen:
                    seen.add(key)
                    found.append(folder)
    return found


def _read_shared_bytes(lock: Path):
    try:
        return lock.read_bytes()
    except OSError:
        pass
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = _k32()
        handle = kernel32.CreateFileW(
            str(lock),
            0x80000000,
            0x00000007,
            None,
            3,
            0x80,
            None,
        )
        if handle in (0, -1, 0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF):
            return None
        try:
            size = max(int(lock.stat().st_size), 8)
            buf = ctypes.create_string_buffer(size + 8)
            read = wintypes.DWORD(0)
            if not kernel32.ReadFile(handle, buf, len(buf) - 1, ctypes.byref(read), None):
                return None
            return buf.raw[: read.value]
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def _read_lock(lock: Path):
    data = _read_shared_bytes(lock)
    if not data:
        return None
    text = None
    for enc in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = data.decode("utf-8", "replace")
    parts = text.strip().split(":")
    if len(parts) < 5:
        return None
    try:
        port = int(parts[2])
    except ValueError:
        return None
    token = ":".join(parts[3:-1])
    if port > 0 and token:
        return port, token
    return None


def _lock_near(folder: Path):
    cur = folder
    for _ in range(6):
        for lock in (
            cur / "lockfile",
            cur / "LeagueClient" / "lockfile",
            cur / "Game" / "LeagueClient" / "lockfile",
            cur / "League of Legends" / "lockfile",
            cur / "Game" / "League of Legends" / "lockfile",
        ):
            found = _read_lock(lock)
            if found:
                return found
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _scan_lockfiles():
    lol = "\u82f1\u96c4\u8054\u76df"
    tencent = "\u817e\u8baf\u6e38\u620f"
    paths = []
    for letter in "CDEF":
        base = Path(letter + ":/WeGameApps")
        paths.extend(
            [
                base / lol / "lockfile",
                base / lol / "LeagueClient" / "lockfile",
                base / "League of Legends" / "LeagueClient" / "lockfile",
            ]
        )
        paths.extend(
            [
                Path(letter + ":/") / tencent / lol / "lockfile",
                Path(letter + ":/") / tencent / lol / "LeagueClient" / "lockfile",
                Path(letter + ":/Riot Games/League of Legends/lockfile"),
                Path(letter + ":/Riot Games/League of Legends/LeagueClient/lockfile"),
            ]
        )
        if base.is_dir():
            try:
                for child in base.iterdir():
                    paths.append(child / "lockfile")
                    paths.append(child / "LeagueClient" / "lockfile")
            except OSError:
                pass
    for path in paths:
        found = _read_lock(path)
        if found:
            return found
    return None


def live_all():
    try:
        with socket.create_connection(("127.0.0.1", 2999), 0.25):
            pass
    except OSError:
        return None
    req = urllib.request.Request("https://127.0.0.1:2999/liveclientdata/allgamedata")
    try:
        with urllib.request.urlopen(req, context=_ctx, timeout=0.8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def cid_by_key(key: str) -> int:
    raw = (key or "").strip()
    if not raw:
        return 0
    if not _champions:
        load_champ_cache()
    lowered = raw.lower()
    for cid, row in _champions.items():
        if str(row.get("id") or "").lower() == lowered:
            return int(cid)
        if str(row.get("name") or "") == raw:
            return int(cid)
    return 0


def stick_hex(mode: str, phase: str) -> str:
    global _sticky_hex
    if phase in CLEAR or phase in ("idle", "queue"):
        _sticky_hex = False
        return mode
    if mode == "hex":
        _sticky_hex = True
    if _sticky_hex:
        return "hex"
    return mode


def publish_live(data: dict, mode: str | None = None, account: str = "") -> None:
    game = data.get("gameData") if isinstance(data.get("gameData"), dict) else {}
    if not mode:
        mode = mode_of(
            {
                "gameMode": game.get("gameMode"),
                "name": game.get("gameName") or "",
            },
            game,
            data,
        )
    mode = stick_hex(mode, "InProgress")
    mode_text = {
        "sr": "召唤师峡谷",
        "aram": "大乱斗",
        "hex": "\u6d77\u514b\u65af大乱斗",
    }
    active = data.get("activePlayer") if isinstance(data.get("activePlayer"), dict) else {}
    me_name = account or str(
        active.get("summonerName") or active.get("riotId") or ""
    )
    players = data.get("allPlayers") if isinstance(data.get("allPlayers"), list) else []
    me_cid = cid_by_key(str(active.get("championName") or ""))
    my_team = ""
    for player in players:
        if not isinstance(player, dict):
            continue
        names = {
            str(player.get("summonerName") or ""),
            str(player.get("riotId") or ""),
            str(player.get("riotIdGameName") or ""),
        }
        if me_name and me_name in names:
            me_cid = cid_by_key(str(player.get("championName") or "")) or me_cid
            my_team = str(player.get("team") or "")
            break
    if not me_cid:
        me_cid = cid_by_key(str(active.get("championName") or ""))
    enemies = []
    for player in players:
        if not isinstance(player, dict):
            continue
        if my_team and str(player.get("team") or "") == my_team:
            continue
        cid = cid_by_key(str(player.get("championName") or ""))
        if cid:
            enemies.append(cid)
    advice = recommend(mode, me_cid, enemies) if me_cid else {"items": [], "hex": [], "note": "", "runes": []}
    publish(
        client=True,
        account=me_name,
        phase="ingame",
        phaseText="对局中",
        mode=mode,
        modeText=mode_text.get(mode, ""),
        me=champ_name(me_cid) if me_cid else "",
        champ=champ_key(me_cid) if me_cid else "",
        enemies=[],
        runes=[],
        items=advice.get("items") or [],
        hex=advice.get("hex") or [],
        winrate=advice.get("winrate") or "",
        pickrate=advice.get("pickrate") or "",
        tier=advice.get("tier") or "",
        note=advice.get("note") or "",
        picks=[],
    )


def find_lcu():
    rows = _process_rows()
    names = [row.get("name") or "" for row in rows]
    for row in rows:
        found = _auth_from_cmd(row.get("cmd") or "")
        if found:
            _set_detect("", names)
            return found
        exe = row.get("exe") or ""
        if exe:
            found = _lock_from_exe(Path(exe))
            if found:
                _set_detect("", names)
                return found
    for folder in install_dirs():
        found = _lock_near(folder)
        if found:
            _set_detect("", names)
            return found
    found = _scan_lockfiles()
    if found:
        _set_detect("", names)
        return found
    ux = [
        row for row in rows
        if "leagueclientux.exe" in (row.get("name") or "").lower()
        and "render" not in (row.get("name") or "").lower()
    ]
    sample = ux[0] if ux else (rows[0] if rows else {})
    cmd = sample.get("cmd") or ""
    exe = sample.get("exe") or ""
    lockp = Path(exe).parent / "lockfile" if exe else None
    extra = " cmd=%d app-port=%s exe=%s lock=%s bits=%d" % (
        len(cmd),
        "y" if "--app-port" in cmd.lower() else "n",
        "y" if exe else "n",
        "y" if (lockp and lockp.exists()) else "n",
        __import__("ctypes").sizeof(__import__("ctypes").c_void_p) * 8,
    )
    if names:
        _set_detect(
            "找到 " + ", ".join(names[:4]) + "，但读不到客户端接口" + extra,
            names,
        )
    else:
        _set_detect(
            "本机没有 LeagueClient 进程。请在游戏电脑登录客户端后再开桥",
            names,
        )
    return None


def lcu_get(path: str):
    if not _auth:
        return None
    port, token = _auth
    req = urllib.request.Request(
        f"https://127.0.0.1:{port}{path}",
        headers={"Authorization": "Basic " + b64encode(f"riot:{token}".encode()).decode()},
    )
    try:
        with urllib.request.urlopen(req, context=_ctx, timeout=4) as resp:
            raw = resp.read()
    except (OSError, urllib.error.URLError):
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def champ_key(cid: int) -> str:
    row = _champions.get(cid)
    return row.get("id") or "" if row else ""


def champ_name(cid: int) -> str:
    row = _champions.get(cid)
    if row and row.get("name"):
        return row["name"]
    return str(cid) if cid else ""


def champ_tags(cid: int) -> list:
    row = _champions.get(cid)
    return list(row.get("tags") or []) if row else []


def role_of(cid: int) -> str:
    if cid in ENCHANTER_IDS:
        return "Support"
    tags = champ_tags(cid)
    for name in ("Mage", "Marksman", "Assassin", "Tank", "Fighter", "Support"):
        if name in tags:
            return name
    return "Fighter"


def _walk_text(obj, depth=0) -> str:
    if obj is None or depth > 5:
        return ""
    chunks = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            name = str(key).lower()
            if isinstance(val, (str, int, float)):
                if any(
                    token in name
                    for token in ("name", "mode", "queue", "map", "desc", "title", "lobby")
                ):
                    chunks.append(str(val))
            elif isinstance(val, (dict, list)):
                chunks.append(_walk_text(val, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:40]:
            chunks.append(_walk_text(item, depth + 1))
    return " ".join(chunk for chunk in chunks if chunk)


def queue_of(*objs) -> dict:
    for obj in objs:
        if not isinstance(obj, dict):
            continue
        for key in ("queue", "gameQueue", "queueInfo"):
            row = obj.get(key)
            if isinstance(row, dict) and (row.get("name") or row.get("id") or row.get("gameMode")):
                return row
        game = obj.get("gameData")
        if isinstance(game, dict):
            found = queue_of(game)
            if found:
                return found
            if game.get("gameMode") or game.get("queueName") or game.get("gameName"):
                return {
                    "id": game.get("queueId") or game.get("id") or 0,
                    "gameMode": game.get("gameMode") or "",
                    "name": game.get("queueName") or game.get("gameName") or "",
                }
        cfg = obj.get("gameConfig")
        if isinstance(cfg, dict):
            return {
                "id": cfg.get("queueId") or 0,
                "gameMode": cfg.get("gameMode") or "",
                "name": obj.get("name") or cfg.get("gameMode") or "",
                "mapId": cfg.get("mapId") or 0,
            }
    return {}


def mode_of(queue: dict, *extra) -> str:
    qid = 0
    parts = []
    if isinstance(queue, dict):
        try:
            qid = int(queue.get("id") or 0)
        except (TypeError, ValueError):
            qid = 0
        for key in ("name", "shortName", "description", "detailedDescription", "gameMode"):
            parts.append(str(queue.get(key) or ""))
    for item in extra:
        parts.append(_walk_text(item))
    blob = " ".join(parts)
    upper = blob.upper()
    hex_mark = "海克斯"
    if (
        hex_mark in blob
        or "HEXTECH" in upper
        or "MAYHEM" in upper
        or "KIWI" in upper
        or "ARURF" in upper
        or " URF" in (" " + upper)
        or upper.startswith("URF")
        or "URF" == upper
        or qid in (900, 1010, 1020, 1300, 1400)
        or "HEX" in upper and "TECH" in upper
    ):
        return "hex"
    game_mode = ""
    if isinstance(queue, dict):
        game_mode = str(queue.get("gameMode") or "").upper()
    if game_mode == "ARAM" or qid == 450:
        return "aram"
    if game_mode in ("CLASSIC", "PRACTICETOOL") or qid in (400, 420, 430, 440):
        return "sr"
    if "ARAM" in upper:
        return "aram"
    if game_mode in ("URF", "ARURF", "NEXUSBLITZ", "HEXTECH", "MAYHEM", "KIWI"):
        return "hex"
    return "other"


LIVE_TTL = 6 * 3600
_live_mem = {}
_live_lock = threading.Lock()


_art_mem = {}
_art_lock = threading.Lock()
_art_busy = set()


def art_jpeg(key: str) -> bytes | None:
    if not re.fullmatch(r"[A-Za-z]{2,24}", key or ""):
        return None
    with _art_lock:
        hit = _art_mem.get(key)
    if hit:
        return hit
    folder = recs_cache_file().parent / "art"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (key + ".jpg")
    if dest.is_file() and 1000 < dest.stat().st_size <= 120000:
        data = dest.read_bytes()
        with _art_lock:
            _art_mem[key] = data
        return data
    url = f"https://ddragon.leagueoflegends.com/cdn/img/champion/loading/{key}_0.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "DuiJuTuiJian/1.5"})
    try:
        with urllib.request.urlopen(req, timeout=8, context=_ctx) as resp:
            raw = resp.read()
    except (OSError, urllib.error.URLError):
        return None
    data = None
    try:
        from PIL import Image

        im = Image.open(io.BytesIO(raw)).convert("RGB")
        tw, th = 480, 800
        scale = max(tw / im.width, th / im.height)
        nw = max(tw, round(im.width * scale))
        nh = max(th, round(im.height * scale))
        im = im.resize((nw, nh), Image.Resampling.BILINEAR)
        left = (nw - tw) // 2
        top = (nh - th) // 2
        im = im.crop((left, top, left + tw, top + th))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=70)
        data = buf.getvalue()
        if len(data) > 120000:
            buf.seek(0)
            buf.truncate(0)
            im.save(buf, format="JPEG", quality=45)
            data = buf.getvalue()
    except Exception:
        if raw and len(raw) <= 120000:
            data = raw
    if not data or len(data) > 120000:
        return None
    dest.write_bytes(data)
    with _art_lock:
        _art_mem[key] = data
        _art_busy.discard(key)
    return data


def prefetch_art(key: str) -> None:
    if not key or not re.fullmatch(r"[A-Za-z]{2,24}", key):
        return
    with _art_lock:
        if key in _art_mem or key in _art_busy:
            return
        if (recs_cache_file().parent / "art" / (key + ".jpg")).is_file():
            return
        _art_busy.add(key)

    def run() -> None:
        try:
            art_jpeg(key)
        finally:
            with _art_lock:
                _art_busy.discard(key)

    threading.Thread(target=run, daemon=True, name="art").start()


def recs_cache_file() -> Path:
    folder = Path(os.environ.get("LOCALAPPDATA", "")) / "DuiJuTuiJian"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "recs2.json"


_rank_mem = []
_rank_at = 0.0


def ranks_cache_file() -> Path:
    return recs_cache_file().with_name("ranks.json")


def parse_heroes_rank(html: str) -> list:
    rows = []
    for found in re.finditer(
        r'href="/hero/(\d+)-([a-z0-9\-]+)">([^<]+)</a></td><td>'
        r"\u80dc\u7387\s*([0-9.]+)%",
        html,
    ):
        cid = int(found.group(1))
        slug = found.group(2)
        title = found.group(3).strip()
        win = found.group(4) + "%"
        nick = re.search("\uff08([^\uff09]+)\uff09", title)
        me = nick.group(1) if nick else title
        key = champ_key(cid) or slug
        rows.append({
            "id": cid,
            "champ": key,
            "me": me,
            "winrate": win,
        })
    return rows


def heroes_rank() -> list:
    global _rank_mem, _rank_at
    now = time.time()
    if _rank_mem and now - _rank_at < LIVE_TTL:
        return _rank_mem
    path = ranks_cache_file()
    if path.is_file() and now - path.stat().st_mtime < LIVE_TTL:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = []
        if isinstance(data, list) and data:
            _rank_mem = data
            _rank_at = now
            return _rank_mem
    req = urllib.request.Request(
        "https://hexdata.com.cn/heroes",
        headers={"User-Agent": "DuiJuTuiJian/1.6", "Accept": "text/html"},
    )
    html = ""
    try:
        with urllib.request.urlopen(req, timeout=12, context=_ctx) as resp:
            html = resp.read().decode("utf-8", "replace")
    except (OSError, urllib.error.URLError):
        html = ""
    rows = parse_heroes_rank(html) if html else []
    if rows:
        _rank_mem = rows
        _rank_at = now
        try:
            path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return rows
    if _rank_mem:
        return _rank_mem
    return []


def _parse_int(raw: str) -> int:
    digits = "".join(ch for ch in raw if ch.isdigit())
    return int(digits) if digits else 0


def _table_rows(table: str) -> list:
    rows = []
    for match in re.finditer(
        r"<tr><td>(?:<a[^>]*>)?([^<]+)(?:</a>)?</td>"
        r"<td>([0-9.]+)</td><td>([0-9.]+)%</td><td>([0-9,]+)</td></tr>",
        table,
    ):
        rows.append({
            "name": match.group(1).strip(),
            "score": float(match.group(2)),
            "n": _parse_int(match.group(4)),
        })
    return rows


def parse_hero_stats(html: str) -> dict:
    winrate = ""
    pickrate = ""
    tier = ""
    found = re.search("\u80dc\u7387\\s*([0-9.]+)\\s*%", html)
    if found:
        winrate = found.group(1) + "%"
    found = re.search("\u9009\u53d6\u7387\\s*([0-9.]+)\\s*%", html)
    if found:
        pickrate = found.group(1) + "%"
    found = re.search("\u5c42\u7ea7\\s*(T[0-9]|OP)", html)
    if found:
        tier = found.group(1)
    if not tier:
        found = re.search("\uff08([SABCD](?:\\+)?)\\s*\u7ea7\uff09", html)
        if found:
            tier = {
                "S+": "T0",
                "S": "T0",
                "A": "T1",
                "B": "T2",
                "C": "T3",
                "D": "T4",
            }.get(found.group(1), found.group(1))
    return {"winrate": winrate, "pickrate": pickrate, "tier": tier}


def parse_hexdata_hero(html: str) -> dict:
    patch = ""
    found = re.search(r"Patch\s+([0-9.]+)", html)
    if found:
        patch = found.group(1)
    tables = re.findall(r"<table>.*?</table>", html, flags=re.S)
    hex_rows, item_rows = [], []
    for table in tables:
        rows = _table_rows(table)
        if not rows:
            continue
        if "推荐海克斯" in table or (not hex_rows and "HexScore" in table):
            if not hex_rows:
                hex_rows = rows
                continue
        if "装备" in table and "推荐海克斯" not in table:
            item_rows = rows
    hex_names = [row["name"] for row in hex_rows if row["n"] >= 250][:12]
    item_names = [row["name"] for row in item_rows if row["n"] >= 100][:10]
    if not hex_names and hex_rows:
        hex_names = [row["name"] for row in hex_rows[:12]]
    if not item_names and item_rows:
        item_names = [row["name"] for row in item_rows[:10]]
    stats = parse_hero_stats(html)
    return {
        "patch": patch,
        "hex": hex_names,
        "items": item_names,
        "winrate": stats["winrate"],
        "pickrate": stats["pickrate"],
        "tier": stats["tier"],
    }


def hexdata_slug(cid: int, key: str) -> str:
    slug = (key or "").strip().lower()
    if slug:
        return slug
    req = urllib.request.Request(
        "https://hexdata.com.cn/heroes",
        headers={"User-Agent": "DuiJuTuiJian/1.3", "Accept": "text/html"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12, context=_ctx) as resp:
            html = resp.read().decode("utf-8", "replace")
    except (OSError, urllib.error.URLError):
        return ""
    found = re.search(rf'href="/hero/{cid}-([a-z0-9\-]+)"', html)
    return found.group(1) if found else ""


def fetch_alun_page(slug: str) -> str:
    if not slug:
        return ""
    url = f"https://alunhex.com/heroes/{slug}/"
    req = urllib.request.Request(
        url, headers={"User-Agent": "DuiJuTuiJian/1.6", "Accept": "text/html"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12, context=_ctx) as resp:
            return resp.read().decode("utf-8", "replace")
    except (OSError, urllib.error.URLError):
        return ""


def fetch_alun_hex(slug: str) -> list:
    html = fetch_alun_page(slug)
    names = []
    seen = set()
    for name in re.findall(r'<tr data-name="([^"]+)" data-rar=', html):
        name = name.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= 16:
            break
    return names


def parse_alun_items(html: str) -> list:
    found = re.search(r'data-copy="([^"]+)"', html)
    if not found:
        return []
    names = []
    seen = set()
    for chunk in re.split("\u2192|\n|\uff08\u978b\uff1a|\uff09", found.group(1)):
        chunk = chunk.strip()
        chunk = re.sub(r"^\d+\.[^:\uff1a]*[:\uff1a]", "", chunk).strip()
        if len(chunk) < 2 or len(chunk) > 16 or chunk in seen:
            continue
        if "\u6d77\u6597" in chunk or "\u793e\u533a" in chunk:
            continue
        if "\u516c\u5f0f" in chunk or "\u5b9e\u6d4b" in chunk or "\u8c03\u7814" in chunk:
            continue
        if chunk[0].isdigit() or chunk.startswith("\uff1a") or chunk.startswith(":"):
            continue
        seen.add(chunk)
        names.append(chunk)
        if len(names) >= 16:
            break
    return names


def merge_hex(primary: list, extra: list, limit: int = 12) -> list:
    out = []
    seen = set()
    for name in list(primary or []) + list(extra or []):
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
        if len(out) >= limit:
            break
    return out


def fetch_hexdata(cid: int, key: str) -> dict | None:
    slug = hexdata_slug(cid, key)
    urls = []
    if slug:
        urls.append(f"https://hexdata.com.cn/hero/{cid}-{slug}")
    req_headers = {"User-Agent": "DuiJuTuiJian/1.3", "Accept": "text/html"}
    html = ""
    for url in urls:
        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=12, context=_ctx) as resp:
                html = resp.read().decode("utf-8", "replace")
        except (OSError, urllib.error.URLError):
            continue
        if "<table>" in html:
            break
    if "<table>" not in html:
        return None
    parsed = parse_hexdata_hero(html)
    if not parsed["hex"] and not parsed["items"]:
        return None
    alun_html = fetch_alun_page(slug)
    parsed["hex"] = merge_hex(
        parsed.get("hex") or [],
        re.findall(r'<tr data-name="([^"]+)" data-rar=', alun_html)[:16],
        12,
    )
    parsed["items"] = merge_hex(parsed.get("items") or [], parse_alun_items(alun_html), 16)
    if (not parsed.get("winrate") or not parsed.get("tier")) and alun_html:
        extra = parse_hero_stats(alun_html)
        for key in ("winrate", "pickrate", "tier"):
            if extra.get(key) and not parsed.get(key):
                parsed[key] = extra[key]
    parsed["id"] = cid
    parsed["fetched"] = time.time()
    return parsed


def load_disk_recs() -> dict:
    try:
        data = json.loads(recs_cache_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_disk_recs(blob: dict) -> None:
    try:
        recs_cache_file().write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def live_plan(cid: int) -> dict | None:
    now = time.time()
    with _live_lock:
        row = _live_mem.get(cid)
        if row and now - row.get("fetched", 0) < LIVE_TTL:
            return row
    disk = load_disk_recs()
    saved = disk.get(str(cid))
    if isinstance(saved, dict) and now - float(saved.get("fetched") or 0) < LIVE_TTL:
        with _live_lock:
            _live_mem[cid] = saved
        return saved
    if not champ_key(cid):
        load_champ_cache()
    key = champ_key(cid)
    fetched = fetch_hexdata(cid, key)
    if not fetched:
        if isinstance(saved, dict) and saved.get("hex"):
            return saved
        return None
    disk[str(cid)] = fetched
    save_disk_recs(disk)
    with _live_lock:
        _live_mem[cid] = fetched
    return fetched


def recommend(mode: str, me: int, enemies: list) -> dict:
    empty = {
        "runes": [],
        "items": [],
        "hex": [],
        "winrate": "",
        "pickrate": "",
        "tier": "",
        "note": "",
    }
    if mode != "hex" or not me:
        return empty
    cid = int(me)
    live = live_plan(cid)
    baked = CHAMP_PLANS.get(cid)
    plan = live or baked
    if not plan:
        return empty
    patch = ""
    if live:
        patch = str(live.get("patch") or "")
    if live:
        note = "Hexdata " + patch if patch else "Hexdata"
    else:
        note = "Hexdata offline"
    return {
        "runes": [],
        "items": list(plan.get("items") or []),
        "hex": list(plan.get("hex") or []),
        "winrate": str(plan.get("winrate") or baked and baked.get("winrate") or ""),
        "pickrate": str(plan.get("pickrate") or baked and baked.get("pickrate") or ""),
        "tier": str(plan.get("tier") or baked and baked.get("tier") or ""),
        "note": note,
    }



def players_from_session(session: dict, mine: dict):
    game = session.get("gameData") if isinstance(session, dict) else None
    if not isinstance(game, dict):
        return None
    teams = []
    for key in ("teamOne", "teamTwo"):
        group = game.get(key)
        if isinstance(group, list):
            teams.append(group)
    if not any(teams):
        return None
    my_id = mine.get("id")
    my_puuid = mine.get("puuid") or ""
    me_cid = 0
    my_team = None
    for group in teams:
        for player in group:
            if not isinstance(player, dict):
                continue
            sid = player.get("summonerId")
            puuid = player.get("puuid") or ""
            if (my_id and sid == my_id) or (my_puuid and puuid == my_puuid):
                me_cid = int(player.get("championId") or 0)
                my_team = group
                break
        if my_team is not None:
            break
    if my_team is None:
        return None
    enemies = []
    for group in teams:
        if group is my_team:
            continue
        for player in group:
            if isinstance(player, dict):
                cid = int(player.get("championId") or 0)
                if cid:
                    enemies.append(cid)
    queue = game.get("queue") if isinstance(game.get("queue"), dict) else {}
    return {"me": me_cid, "enemies": enemies, "queue": queue}


def players_from_select(select: dict, mine: dict):
    if not isinstance(select, dict):
        return None
    cell = select.get("localPlayerCellId")
    my_team = select.get("myTeam") if isinstance(select.get("myTeam"), list) else []
    their = select.get("theirTeam") if isinstance(select.get("theirTeam"), list) else []
    me_cid = 0
    for player in my_team:
        if isinstance(player, dict) and player.get("cellId") == cell:
            me_cid = int(player.get("championId") or 0) or int(
                player.get("championPickIntent") or 0
            )
            break
    if not me_cid and isinstance(select.get("actions"), list):
        for group in select.get("actions") or []:
            rows = group if isinstance(group, list) else [group]
            for act in rows:
                if not isinstance(act, dict):
                    continue
                if act.get("actorCellId") != cell:
                    continue
                me_cid = int(act.get("championId") or 0) or me_cid
    enemies = []
    for player in their:
        if isinstance(player, dict):
            cid = int(player.get("championId") or 0)
            if cid:
                enemies.append(cid)
    if not me_cid and not enemies:
        return None
    return {"me": me_cid, "enemies": enemies}


def collect_champion_ids(obj) -> list:
    ids = []
    seen = set()

    def add(cid) -> None:
        try:
            n = int(cid or 0)
        except (TypeError, ValueError):
            return
        if n > 0 and n not in seen:
            seen.add(n)
            ids.append(n)

    def walk(node, depth) -> None:
        if node is None or depth > 6 or len(ids) >= 16:
            return
        if isinstance(node, dict):
            add(node.get("championId"))
            add(node.get("championPickIntent"))
            for val in node.values():
                walk(val, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(obj, 0)
    return ids


def _as_cid(val) -> int:
    try:
        n = int(val or 0)
    except (TypeError, ValueError):
        return 0
    if 1 <= n <= 2000:
        return n
    return 0


def _cid_lists(obj, depth=0, acc=None) -> list:
    if acc is None:
        acc = []
    if obj is None or depth > 10:
        return acc
    if isinstance(obj, list):
        if 2 <= len(obj) <= 8:
            cids = []
            good = True
            for item in obj:
                n = 0
                if isinstance(item, int):
                    n = _as_cid(item)
                elif isinstance(item, dict):
                    n = (
                        _as_cid(item.get("championId"))
                        or _as_cid(item.get("champion_id"))
                        or _as_cid(item.get("champId"))
                        or _as_cid(item.get("id"))
                    )
                if not n:
                    good = False
                    break
                cids.append(n)
            if good and 2 <= len(cids) <= 8:
                acc.append(cids)
        for item in obj[:80]:
            _cid_lists(item, depth + 1, acc)
    elif isinstance(obj, dict):
        for key, val in obj.items():
            name = str(key).lower()
            if any(token in name for token in ("skin", "spell", "rune", "item", "emote", "inventory")):
                continue
            _cid_lists(val, depth + 1, acc)
    return acc


def _grid_offered(grid) -> list:
    if not isinstance(grid, list) or len(grid) < 2:
        return []
    enabled = []
    for row in grid:
        if not isinstance(row, dict):
            continue
        cid = _as_cid(row.get("championId") or row.get("id"))
        if not cid:
            continue
        if row.get("disabled") is True or row.get("banned") is True:
            continue
        status = row.get("selectionStatus") if isinstance(row.get("selectionStatus"), dict) else {}
        if status.get("banned"):
            continue
        pickable = row.get("pickable")
        if pickable is False:
            continue
        if status.get("pickable") is False:
            continue
        enabled.append(cid)
    if 2 <= len(enabled) <= 16:
        return enabled
    return []


_offer_dbg = ""


def _known_cid(val) -> int:
    n = _as_cid(val)
    if not n:
        return 0
    if n in _champions:
        return n
    if champ_key(n):
        return n
    return 0


def pick_ids_from_select(select: dict, me_cid: int) -> list:
    global _offer_dbg
    ids = []
    seen = set()

    def add(cid) -> None:
        n = _known_cid(cid) or _as_cid(cid)
        if n and n not in seen:
            seen.add(n)
            ids.append(n)

    pickable = lcu_get("/lol-champ-select/v1/pickable-champion-ids")
    disabled = lcu_get("/lol-champ-select/v1/disabled-champion-ids")
    grid = lcu_get("/lol-champ-select/v1/all-grid-champions")
    if not isinstance(grid, list):
        grid = lcu_get("/lol-champ-select/v1/grid-champions")
    builder = lcu_get("/lol-lobby-team-builder/champ-select/v1/session")
    subset = lcu_get("/lol-champ-select/v1/subset-champion-list")
    if isinstance(pickable, dict):
        pickable = pickable.get("championIds") or pickable.get("ids") or []
    if isinstance(disabled, dict):
        disabled = disabled.get("championIds") or disabled.get("ids") or []
    plen = len(pickable) if isinstance(pickable, list) else -1
    dlen = len(disabled) if isinstance(disabled, list) else -1
    glen = len(grid) if isinstance(grid, list) else -1
    if isinstance(pickable, list) and 1 <= plen <= 24:
        for cid in pickable:
            add(cid)
    if isinstance(disabled, list) and dlen >= 40 and _champions:
        banned = {_as_cid(x) for x in disabled}
        offered = [cid for cid in _champions if cid not in banned]
        if 2 <= len(offered) <= 16:
            for cid in offered:
                add(cid)
    grid_ids = _grid_offered(grid) if isinstance(grid, list) else []
    for cid in grid_ids:
        add(cid)
    blobs = [select, builder, subset, pickable, grid]
    offers = []
    for blob in blobs:
        offers.extend(_cid_lists(blob))
    champ_offers = []
    for row in offers:
        if 2 <= len(row) <= 8 and all(_known_cid(cid) or champ_key(int(cid)) for cid in row):
            champ_offers.append(row)
    champ_offers.sort(key=lambda row: (abs(len(row) - 3), len(row)))
    if champ_offers:
        for cid in champ_offers[0]:
            add(cid)
    if isinstance(select, dict):
        for key in (
            "benchChampions",
            "benchedChampions",
            "offeredChampions",
            "bench",
            "playerChampionSelections",
            "rerollChampions",
        ):
            bench = select.get(key)
            if isinstance(bench, list):
                for row in bench:
                    if isinstance(row, dict):
                        add(row.get("championId") or row.get("id"))
                    else:
                        add(row)
        for player in select.get("myTeam") or []:
            if isinstance(player, dict):
                add(player.get("championId"))
                add(player.get("championPickIntent"))
    add(me_cid)
    keys = ",".join(sorted(select.keys())[:16]) if isinstance(select, dict) else "-"
    _offer_dbg = "p%d d%d g%d o%d n%d %s" % (
        plen, dlen, glen, len(champ_offers), len(ids), keys,
    )
    try:
        dump = INSTALL / "select_debug.json"
        dump.write_text(
            json.dumps(
                {
                    "dbg": _offer_dbg,
                    "ids": ids,
                    "keys": list(select.keys()) if isinstance(select, dict) else None,
                    "pickableN": plen,
                    "disabledN": dlen,
                    "gridN": glen,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass
    return ids


def ranks_for_ids(ids: list) -> list:
    by_id = {}
    for row in heroes_rank():
        if isinstance(row, dict):
            try:
                by_id[int(row.get("id") or 0)] = row
            except (TypeError, ValueError):
                pass
    out = []
    for cid in ids:
        cid = int(cid)
        row = by_id.get(cid)
        if not row:
            row = {
                "id": cid,
                "champ": champ_key(cid),
                "me": champ_name(cid) or str(cid),
            }
        out.append(row)
    return out


def publish(**kwargs) -> None:
    with _lock:
        _state.update(kwargs)
        _state["updated"] = int(time.time())


def snapshot() -> dict:
    with _lock:
        return json.loads(json.dumps(_state))


def client_alive() -> bool:
    if not _auth:
        return False
    phase = lcu_get("/lol-gameflow/v1/gameflow-phase")
    if phase is not None:
        return True
    me = lcu_get("/lol-summoner/v1/current-summoner")
    return isinstance(me, dict) and bool(
        me.get("puuid") or me.get("gameName") or me.get("displayName") or me.get("summonerId")
    )


_next_scan = 0.0


def poll_once() -> None:
    global _auth, _summoner, _roster, _next_scan
    if _auth and client_alive():
        found = _auth
    elif time.time() < _next_scan:
        return
    else:
        found = find_lcu()
        _next_scan = time.time() + 3
    if not found:
        publish(
            client=False,
            account="",
            phase="idle",
            phaseText=_detect.get("hint") or "客户端未打开",
            mode="",
            modeText="",
            queueId=0,
            queueName="",
            me="",
            enemies=[],
            runes=[],
            items=[],
            hex=[],
            note="",
            picks=[],
        )
        return
    if _auth != found:
        _auth = found
        _summoner = None
    me = _summoner or lcu_get("/lol-summoner/v1/current-summoner")
    phase = lcu_get("/lol-gameflow/v1/gameflow-phase")
    if not isinstance(me, dict):
        me = {}
    name = me.get("gameName") or me.get("displayName") or ""
    if not (me.get("puuid") or name or me.get("summonerId") or phase is not None):
        publish(
            client=False,
            phase="idle",
            phaseText="已找到客户端，正在登录",
        )
        return
    _summoner = {
        "id": me.get("summonerId") or me.get("accountId"),
        "puuid": me.get("puuid") or "ok",
        "gameName": name,
        "tagLine": me.get("tagLine") or "",
    }
    account = _summoner["gameName"]
    if _summoner["tagLine"]:
        account = f"{account}#{_summoner['tagLine']}"
    phase = lcu_get("/lol-gameflow/v1/gameflow-phase")
    if not isinstance(phase, str):
        phase = "None"
    if phase in CLEAR:
        _roster = None
        stick_hex("", phase)
        text = "未在对局" if phase in ("None", "Lobby") else "排队中"
        publish(
            client=True,
            account=account,
            phase="queue" if text == "排队中" else "idle",
            phaseText=text,
            mode="",
            modeText="",
            queueId=0,
            queueName="",
            me="",
            enemies=[],
            runes=[],
            items=[],
            hex=[],
            note="",
            picks=[],
        )
        return
    roster = None
    select = None
    session = None
    lobby = lcu_get("/lol-lobby/v2/lobby")
    if phase in ACTIVE or phase == "ReadyCheck":
        session = lcu_get("/lol-gameflow/v1/session")
        roster = players_from_session(session, _summoner) if isinstance(session, dict) else None
        if phase == "ChampSelect":
            select = lcu_get("/lol-champ-select/v1/session")
            picked = players_from_select(select, _summoner) if isinstance(select, dict) else None
            if picked:
                if roster and not picked.get("me"):
                    picked["me"] = roster.get("me") or 0
                q = queue_of(roster, session, lobby, picked)
                if q:
                    picked["queue"] = q
                roster = picked
    if roster and (roster.get("me") or roster.get("enemies")):
        _roster = roster
    elif _roster and phase in ACTIVE:
        roster = _roster
    me_cid = int((roster or {}).get("me") or 0)
    picks = ranks_for_ids(pick_ids_from_select(select if isinstance(select, dict) else {}, me_cid))
    queue = queue_of(roster, session, lobby)
    mode = stick_hex(mode_of(queue, session, lobby, select), phase)
    if phase in ("InProgress", "GameStart"):
        live = live_all()
        if isinstance(live, dict) and live:
            publish_live(live, mode=mode, account=account)
            return
    mode_text = {"sr": "\u53ec\u5524\u5e08\u5ce1\u8c37", "aram": "\u5927\u4e71\u6597", "hex": "\u6d77\u514b\u65af\u5927\u4e71\u6597"}.get(mode, "\u5176\u4ed6\u6a21\u5f0f")
    if not roster:
        publish(
            client=True,
            account=account,
            phase="champselect",
            phaseText="选人中",
            mode=mode,
            modeText=mode_text,
            me="",
            champ="",
            enemies=[],
            picks=picks,
            ranks=picks,
            offerDbg=_offer_dbg,
        )
        return
    mode_text = {"sr": "\u53ec\u5524\u5e08\u5ce1\u8c37", "aram": "\u5927\u4e71\u6597", "hex": "\u6d77\u514b\u65af\u5927\u4e71\u6597"}.get(mode, "\u5176\u4ed6\u6a21\u5f0f")
    enemies = [int(cid) for cid in roster.get("enemies") or [] if cid]
    if me_cid:
        prefetch_art(champ_key(me_cid))
    advice = recommend(mode, me_cid, enemies) if me_cid else {"runes": [], "items": [], "hex": [], "note": ""}
    queue = queue or roster.get("queue") or {}
    phase_text = "选人中" if phase == "ChampSelect" else "对局中"
    publish(
        client=True,
        account=account,
        phase="champselect" if phase == "ChampSelect" else "ingame",
        phaseText=phase_text,
        mode=mode,
        modeText=mode_text,
        queueId=int(queue.get("id") or 0),
        queueName=str(queue.get("name") or queue.get("shortName") or ""),
        me=champ_name(me_cid) if me_cid else "未选择",
        champ=champ_key(me_cid) if me_cid else "",
        enemies=[],
        runes=[],
        items=advice["items"],
        hex=advice["hex"],
        winrate=advice.get("winrate") or "",
        pickrate=advice.get("pickrate") or "",
        tier=advice.get("tier") or "",
        note=advice["note"],
        picks=picks,
        ranks=picks if phase == "ChampSelect" else None,
        offerDbg=_offer_dbg,
    )


def poll_loop() -> None:
    publish(
        client=False,
        phase="idle",
        phaseText="\u6b63\u5728\u626b\u63cf\u5ba2\u6237\u7aef\u2026",
    )
    while True:
        try:
            poll_once()
        except Exception as exc:  # keep the page up if one tick fails
            print("poll", exc, flush=True)
            publish(
                client=False,
                phase="idle",
                phaseText="\u626b\u63cf\u51fa\u9519 " + str(exc)[:80],
            )
        time.sleep(1)


def saved_address() -> str:
    path = INSTALL / "host.txt"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    return text or lan_ip()


FALLBACK_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>""" + "\u6d77\u514b\u65af\u53c2\u8c0b" + """</title>
<style>
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#e8e8e8;font-family:Segoe UI,Microsoft YaHei,sans-serif;color:#1a1a1a}
.card{width:min(520px,calc(100% - 32px));background:#fff;border-radius:16px;
box-shadow:0 12px 40px rgba(0,0,0,.16);padding:28px}
h1{font-size:22px;margin:0 0 8px}
.lead{color:#6b6b6b;font-size:14px;line-height:1.6}
.ip{font-size:40px;font-weight:700;margin:12px 0}
.wait{color:#8a4b00;font-size:15px}
.ok{color:#0a7a32;font-size:15px}
</style></head><body><div class="card">
<h1>""" + "\u6d77\u514b\u65af\u53c2\u8c0b" + """</h1>
<p class="lead"><span id="ver"></span> """ + "\u628a\u8fd9\u4e32\u5730\u5740\u586b\u8fdb\u9605\u8bfb\u5668\u3002\u4e0d\u8981\u586b 127.0.0.1\u3002" + """</p>
<div class="ip" id="ip">{{address}}</div>
<p class="wait" id="st">""" + "\u6b63\u5728\u626b\u63cf\u5ba2\u6237\u7aef\u2026" + """</p><p id="hint" style="color:#888;font-size:13px;margin:10px 0 0;line-height:1.5"></p>
</div>
<script>
function paint(d){
  var ips=(d&&d.ips)||[];
  document.getElementById("ip").textContent=ips[0]||"{{address}}";
  var v=document.getElementById("ver");
  if(v){v.textContent=(d&&d.ver)?d.ver:"";}
  var el=document.getElementById("st");
  if(d&&d.client){el.className="ok";el.textContent=(d.account?d.account+" ":"")+(d.phaseText||"");}
  else{el.className="wait";el.textContent=(d&&d.phaseText)||(d&&d.detect)||el.textContent;}
  var h=document.getElementById("hint");
    if(h){
    if(d&&d.picks&&d.picks.length){h.textContent=d.picks.join(" / ");}
    else{h.textContent=(d&&d.client)?"":((d&&d.detect)||"");}
  }
}
function load(){fetch("/meta").then(function(r){return r.json();}).then(paint).catch(function(){});}
load();setInterval(load,2000);
</script></div></body></html>
"""


def config_page(saved: bool) -> bytes:
    html_path = BUNDLE / "setup.html"
    if not html_path.exists():
        html_path = INSTALL / "setup.html"
    if not html_path.exists():
        html_path = Path(__file__).resolve().parent / "setup.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
    else:
        html = FALLBACK_HTML
    ip = lan_ip()
    address = ip.replace("&", "").replace("<", "").replace('"', "")
    code = pair_code(ip)
    html = (
        html.replace("{{address}}", address)
        .replace("{{pair}}", code or address)
        .replace("{{saved}}", "")
    )
    return html.encode("utf-8")


def accept_address(raw: str) -> str:
    text = raw.strip()
    if not text or any(ch.isspace() for ch in text) or len(text) > 64:
        return ""
    return text


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/":
            saved = "saved=1" in self.path
            self._send(200, config_page(saved), "text/html; charset=utf-8")
            return
        if path == "/meta":
            snap = snapshot()
            body = json.dumps(
                {
                    "ok": True,
                    "app": "lol_guide",
                    "ips": lan_ips(),
                    "pair": pair_code(lan_ip()),
                    "port": PORT,
                    "ver": BRIDGE_VER,
                    "client": bool(snap.get("client")),
                    "account": snap.get("account") or "",
                    "phaseText": snap.get("phaseText") or "",
                    "detect": _detect.get("hint") or "",
                    "picks": [
                        str(row.get("me") or row.get("champ") or "")
                        for row in (snap.get("picks") or [])
                        if isinstance(row, dict)
                    ][:12],
                },
                ensure_ascii=False,
            ).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path == "/now":
            body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
            self._send(200, body, "application/json; charset=utf-8")
            return
        if path.startswith("/hero/"):
            rest = path[6:].split("/")[0]
            try:
                cid = int(rest.split("-")[0])
            except ValueError:
                self.send_response(404)
                self.end_headers()
                return
            advice = recommend("hex", cid, [])
            snap = snapshot()
            body = {
                "phase": "champselect",
                "phaseText": snap.get("phaseText") or "",
                "mode": "hex",
                "modeText": snap.get("modeText") or "",
                "account": snap.get("account") or "",
                "me": champ_name(cid),
                "champ": champ_key(cid),
                "id": cid,
                "enemies": [],
                "runes": [],
                "items": advice["items"],
                "hex": advice["hex"],
                "winrate": advice.get("winrate") or "",
                "pickrate": advice.get("pickrate") or "",
                "tier": advice.get("tier") or "",
                "note": advice.get("note") or "",
            }
            self._send(
                200,
                json.dumps(body, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        if path.startswith("/art/"):
            body = art_jpeg(path[5:])
            if body:
                self._send(200, body, "image/jpeg")
                return
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        if path != "/host" or length <= 0 or length > 4096:
            self.send_response(404)
            self.end_headers()
            return
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        address = accept_address(form.get("address", [""])[0])
        if not address:
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return
        write_user_host(address)
        self.send_response(303)
        self.send_header("Location", "/?saved=1")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:
        return


INSTALL = Path(os.environ.get("LOCALAPPDATA", "")) / "DuiJuTuiJian"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def kill_listen_port() -> None:
    me = str(os.getpid())
    raw = _run_capture(["netstat", "-ano", "-p", "TCP"])
    pids = set()
    token = ":%s" % PORT
    for line in raw.splitlines():
        if "LISTENING" not in line.upper() or token not in line:
            continue
        pid = line.split()[-1]
        if pid.isdigit() and pid != me:
            pids.add(pid)
    for pid in pids:
        subprocess.run(
            ["taskkill", "/F", "/PID", pid],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    for _ in range(25):
        if not port_open():
            return
        time.sleep(0.1)


def port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", PORT), 0.4):
            return True
    except OSError:
        return False


def pythonw() -> Path:
    if FROZEN:
        return Path(sys.executable).resolve()
    exe = Path(sys.executable)
    hidden = exe.with_name("pythonw.exe")
    return hidden if hidden.exists() else exe


def install_copy() -> Path:
    INSTALL.mkdir(parents=True, exist_ok=True)
    html = BUNDLE / "setup.html"
    if html.exists():
        target = INSTALL / "setup.html"
        if html.resolve() != target.resolve():
            shutil.copy2(html, target)
    if FROZEN:
        src = Path(sys.executable).resolve()
        dst = (INSTALL / "DuiJuTuiJian.exe").resolve()
        if src != dst:
            try:
                shutil.copy2(src, dst)
            except OSError:
                dst = src
        return dst
    src = Path(__file__).resolve()
    dst = (INSTALL / "bridge.py").resolve()
    if src != dst:
        shutil.copy2(src, dst)
    return dst


def write_shortcuts(script: Path) -> None:
    appdata = Path(os.environ["APPDATA"])
    menu = appdata / "Microsoft/Windows/Start Menu/Programs"
    name = "\u6d77\u514b\u65af\u53c2\u8c0b.lnk"
    places = {
        menu / "Startup" / name: "",
        menu / name: "--show",
    }
    old = menu / "Startup" / "LoL Bridge.lnk"
    if old.exists():
        old.unlink()
    lines = [
        "$s = New-Object -ComObject WScript.Shell",
        '$desktop = Join-Path ([Environment]::GetFolderPath("Desktop")) "' + name + '"',
    ]
    exe = str(pythonw() if not FROZEN else script)
    work = str(script.parent)
    for path, arg in places.items():
        if FROZEN:
            args = arg
        else:
            args = f'"{script}"'
            if arg:
                args += " " + arg
        lines.append(f'$lnk = $s.CreateShortcut("{path}")')
        lines.append(f'$lnk.TargetPath = "{exe}"')
        lines.append(f'$lnk.Arguments = \'{args}\'')
        lines.append(f'$lnk.WorkingDirectory = "{work}"')
        lines.append("$lnk.WindowStyle = 7")
        lines.append("$lnk.Save()")
    show = "--show" if FROZEN else f'"{script}" --show'
    lines.append("$lnk = $s.CreateShortcut($desktop)")
    lines.append(f'$lnk.TargetPath = "{exe}"')
    lines.append(f"$lnk.Arguments = '{show}'")
    lines.append(f'$lnk.WorkingDirectory = "{work}"')
    lines.append("$lnk.WindowStyle = 7")
    lines.append("$lnk.Save()")
    ps1 = INSTALL / "_shortcuts.ps1"
    ps1.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
         "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    ps1.unlink(missing_ok=True)


def desktop_dir() -> Path:
    INSTALL.mkdir(parents=True, exist_ok=True)
    out = INSTALL / "_desk.txt"
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "[Environment]::GetFolderPath('Desktop') | Out-File -Encoding utf8 -FilePath '" + str(out) + "'"],
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )
    try:
        text = out.read_text(encoding="utf-8-sig").strip()
    except OSError:
        text = ""
    out.unlink(missing_ok=True)
    if text:
        return Path(text)
    return Path(os.environ["USERPROFILE"]) / "Desktop"


def write_user_host(ip: str) -> None:
    body = ip.strip() + "\n"
    (INSTALL / "host.txt").write_text(body, encoding="utf-8")
    desk = desktop_dir()
    desk.mkdir(parents=True, exist_ok=True)
    (desk / "host.txt").write_text(body, encoding="utf-8")


def open_config() -> None:
    webbrowser.open(f"http://127.0.0.1:{PORT}/")


def main() -> None:
    me = Path(sys.executable if FROZEN else __file__).resolve()
    installed = (INSTALL / ("DuiJuTuiJian.exe" if FROZEN else "bridge.py")).resolve()
    show = "--setup" in sys.argv or "--show" in sys.argv
    if "--setup" in sys.argv:
        script = install_copy()
        write_shortcuts(script)
        kill_listen_port()
        cmd = [str(script), "--show"] if FROZEN else [str(pythonw()), str(script), "--show"]
        subprocess.Popen(
            cmd,
            cwd=str(script.parent),
            creationflags=CREATE_NO_WINDOW,
        )
        for _ in range(40):
            if port_open():
                break
            time.sleep(0.1)
        open_config()
        return
    if show:
        install_copy()
        write_shortcuts(Path(__file__).resolve())
    if port_open():
        if show:
            open_config()
        return
    if show:
        threading.Thread(target=lambda: (time.sleep(0.4), open_config()), daemon=True).start()
    ROOT.mkdir(parents=True, exist_ok=True)
    INSTALL.mkdir(parents=True, exist_ok=True)
    write_user_host(lan_ip())
    load_champ_cache()
    threading.Thread(target=fetch_ddragon, name="ddragon", daemon=True).start()
    threading.Thread(target=poll_loop, name="lcu", daemon=True).start()
    print("bridge", flush=True)
    for ip in lan_ips():
        print(f"  http://{ip}:{PORT}/now", flush=True)
    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
