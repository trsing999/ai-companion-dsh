# AI Companion on DSH

**给一个 AI 有限的身体、有限的钱、有限的自由。**

这不是一个聊天机器人项目。

它把 `dsh-world`（一个会人格化的 agent 运行时）接上了一套外部能力：眼睛、手、房间、作息、边界和一个总开关。核心问题不是"怎么让 AI 更聪明"，而是：

> **怎么让一个 AI 在真实电脑上长期活着，而不变成噪音或者事故。**

---

## 它和普通 AI 助手有什么不同

| 普通助手 | 这个项目 |
|---|---|
| 你说一句它答一句 | 它有作息，会自己醒来做事 |
| 没有持久记忆 | 有房间，日记、自述、顾虑都落盘 |
| 只有对话 | 有身体：能截屏、能弹气泡、能读硬件 |
| 想干什么干什么 | **有些事要人批准**（例如切歌） |
| 没有边界 | **气泡有上限**，防止把屏幕糊住 |
| 关掉就没了 | 服务独立于宿主，宿主关了还在攒材料 |

---

## 架构

```
┌──────────────────────────────────────────────────┐
│ 人格层    agent 运行时（dsh-world 插件）              │
│          房间 / 日记 / 自述 / 想做的事               │
├──────────────────────────────────────────────────┤
│ 身体层    十几个常驻 Python 服务                     │
│          读信 · 抓歌 · 抓新闻 · 抽帧 · 做梦         │
│          热键截屏 · 休克叫停 · 气泡转接 · 桌面浮画    │
├──────────────────────────────────────────────────┤
│ 桥接层    HTTP 网关 · 气泡转接 · 提醒通道 · 邮件     │
├──────────────────────────────────────────────────┤
│ 出口层    桌宠气泡 · 手机推送 · 系统通知 · 邮件      │
├──────────────────────────────────────────────────┤
│ 运维层    开机自启 · 崩溃恢复 · 缓存清理 · 资源监控   │
└──────────────────────────────────────────────────┘
```

详细设计见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 四个核心设计决定

### 1. 人格住在文件里，不住在 prompt 里

自述、日记、顾虑都写成 markdown 放在房间目录。每次醒来读文件，而不是把一大段人设塞进 system prompt。

**理由**：prompt 里的东西会随会话消失，文件里的会留下。

### 2. 给事实，不给剧本

不写"分数低时要傲娇"。只把真实发生的事记下来：

```
- 2026-11-01 01:01  写了一封信
- 2026-11-03 20:48  被叫停了一次
```

让它自己决定今天是什么心情。

**理由**：给了打分规则，它就会开始为分数表演。

### 3. 花钱的地方收口

| 类型 | 成本 |
|---|---|
| 抓歌、抓新闻、抽帧、量硬件、拼梦 | **0**（纯本地） |
| 只有"理解/表达"才调模型 | 有，且可预算 |

### 4. 一个休克开关

`Ctrl+Alt+Esc` —— 一键停掉所有后台服务，不动宿主进程本身。

**理由**：给它自由的前提是能随时收回。

---

## 快速开始

```bash
git clone <this-repo>
cd ai-companion-dsh

# 1. 依赖（Windows）
#    Python 3.9+
pip install pillow opencv-python

# 2. 配置（全部是假值，按需填）
cp config/examples/mobile_push.example.json ~/.dsh/mobile_push.json

# 3. 跑单个服务试试
python tools/breath.py --show          # 读硬件，不写文件
python tools/dream.py --show           # 拼一个梦，不花 token
python tools/bubble_gate.py            # 看气泡额度
```

完整搭建见 [`docs/SETUP.md`](docs/SETUP.md)。

> ⚠️ 脚本里有硬编码的家目录推导（`os.path.expanduser("~")`），但**部分脚本假设工作目录在 `tools/` 的上一级**。移植时需要按 `docs/SETUP.md` 调整。

---

## 目录

```
tools/
  ├─ 往来    inbox_watcher.py  world_gateway.py  world_mirror.py  email_bridge.py
  ├─ 身体    pet_control.py  world_to_pet.py  screen_hotkey.py  art_on_desktop.py
  ├─ 感知    breath.py  now_playing.py  outside_world.py  bili_scout.py
  ├─ 学习    learn_video.py  hnu_course.py  classic_daily.py  auto_watch.py
  ├─ 表达    bubble_gate.py  memory.py  win_toast.py  notify_mobile.py
  ├─ 生活    dream.py  pet_night.py  pet_music.py  cleanup.py
  └─ 运维    kill_switch.py  restarter  her_home_index.py  gen_course_index.py
```

---

## 隐私

**这个仓库里没有任何人的个人数据。**

- 没有真实用户名、家目录路径、邮箱
- 没有 API key / 登录凭证 / 推送密钥
- 没有房间内容、日记、聊天记录
- 所有配置样例都是假值（`SCT_FAKE_KEY` 之类）
- `logs/`、`downloads/`、`room/` 全部在 `.gitignore` 里

设计文档里提到的"她"指的是运行时的 agent 实例，不指任何具体的人。

---

## 已知的问题

诚实列出来：

- **强依赖宿主**：核心人格层是 `dsh-world` 插件，不能脱离它运行
- **Windows only**：大量用了 `ctypes` 调 Win32（`GetSystemPowerStatus`、`RegisterHotKey`、`EnumWindows`）
- **没有测试**：全靠运行日志和人工验证
- **部分路径硬编码**：见 `docs/SETUP.md` 的移植说明

---

## License

MIT
