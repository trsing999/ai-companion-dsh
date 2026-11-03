# 从零搭建

## 前置

| 需要 | 说明 |
|---|---|
| Windows 10/11 | 大量用了 Win32 API（`ctypes`），Linux/macOS 需要重写 |
| Python 3.9+ | 调试时用的是 3.11 |
| [DSH](https://github.com/) + `dsh-world` 插件 | 人格层宿主 |
| `dsh-pet` 插件（可选） | 想要桌面气泡才需要 |

Python 依赖：

```bash
pip install pillow opencv-python
```

**只装两个。** 其余全部标准库（包括硬件读取、HTTP 服务、文件锁）。

---

## 一、目录约定

脚本假设这个结构：

```
<任意目录>/
└─ tools/          ← 所有 .py 都放这儿
   ├─ inbox_watcher.py
   ├─ breath.py
   └─ ...
```

运行时会在 `<上一级>/logs/` 里写日志，在 `<上一级>/downloads/` 里放下载的视频。

**所有脚本都用 `os.path.expanduser("~")` 推导家目录，不写死用户名。** 但有几个脚本假设当前工作目录是 `<上一级>`，所以启动时要 `cd` 到那里：

```bash
cd <项目根>
python tools/breath.py --loop
```

---

## 二、配置清单

全部放在 `~/.dsh/` 下。样例见 `config/examples/`。

| 文件 | 用途 | 必需 |
|---|---|---|
| `mobile_push.json` | 手机推送（Server酱 / 企业微信机器人） | 可选 |
| `email_bridge.json` | 邮件收发 | 可选 |
| `mobile_approval.json` | 手机端审批 | 可选 |
| `bili/session.json` | B 站登录态（只看课用，只读） | 可选 |
| 宿主的 `bridge.json` | 由宿主自动生成，**不要手写** | 必需 |

**安全**：这些文件都在 `.gitignore` 里，永远不要提交。

---

## 三、启动顺序

```
1. 宿主（dsh-world）先起来
   → 它会生成 bridge.json，里面有 origin 和 token
   → 所有桥接脚本都靠它找宿主

2. 常驻服务
   → inbox_watcher.py      读信 / 定时任务
   → world_gateway.py      OpenAI 兼容网关（如果要外部客户端接入）
   → world_to_pet.py       气泡转接（要 dsh-pet）
   → email_bridge.py       邮件
   → screen_hotkey.py      热键截屏
   → kill_switch.py        休克热键
   → breath.py --loop      每 10 分钟量一次硬件
   → dream.py --loop       每晚 23:30 做一个梦
```

**顺序要求**：宿主必须先起来，否则桥接脚本找不到 `origin`。

---

## 四、移植到别的机器

这一步不能跳过。有几类地方需要改：

### 1. 家目录

大部分脚本已经是：

```python
HOME = os.path.expanduser("~")
DSH = os.path.join(HOME, ".dsh")
```

如果你的 `dsh-world` 世界不在 `~/.dsh/worlds/default`，改这行。

### 2. 工作目录假设

有些脚本写日志到「上一级目录」：

```python
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "logs", "xxx.log")
```

保持 `tools/` 放在项目根下即可，不用改。

### 3. Python 解释器路径

Windows 上如果同时装了多个 Python，启动脚本里要写**绝对路径**：

```
C:\Python311\python.exe
```

### 4. 中文路径

**这是最坑的一条**，踩过：

- `cmd` 文件里写中文路径会被 GBK 编码弄坏 → **`.cmd` 里只用 ASCII**
- Python 源码带中文时需要 **UTF-8**（Windows 上不加 BOM 更安全）
- 通过 PowerShell 传中文参数容易变成 `??????` → 改用 UTF-8 字节或直接调 Python

### 5. 热键冲突

`Ctrl+Alt+S`（截屏）和 `Ctrl+Alt+Esc`（休克）如果被别的程序占了，改脚本里的 `DEFAULT_KEY`。

---

## 五、验证装好了没有

```bash
# 1. 硬件读取（不写文件）
python tools/breath.py --show
# → 应该看到 电量 / 处理器 / 内存 三行

# 2. 做梦（不花钱）
python tools/dream.py --show
# → 应该看到一段把房间文件碎片拼起来的话

# 3. 气泡限流
python tools/bubble_gate.py
# → {"最近60秒": 0, "上限": 2, "还能说": 2}

# 4. 休克开关（危险，会停掉所有服务）
python tools/kill_switch.py --now
# → 只有在你确认真要停的时候跑
```

---

## 六、开机自启（可选）

Windows 上最省事的做法：把启动命令放进

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\
```

一个 `.cmd` 里，每行一个：

```
start "" "<python>" "<项目根>\tools\inbox_watcher.py"
```

注意 `.cmd` 内容**只用 ASCII**（见上面第 4 条）。

---

## 七、出问题看哪儿

```
<项目根>\logs\      ← 每个脚本都有自己的日志
```

| 症状 | 先看 |
|---|---|
| 气泡不弹 | `world_to_pet.log`、`bubble_rate.json` |
| 推送不到手机 | `notify_mobile.log`（看返回的 code） |
| 热键没反应 | `screen_hotkey.log`、`kill_switch.log` |
| 拉不到课 | `learn_video.log` |
| 服务莫名没了 | `kill_switch.log`（是不是被叫停了） |
