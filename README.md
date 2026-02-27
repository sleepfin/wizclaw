# wizclaw

Bridge daemon，将本地 OpenClaw agent 连接到云端 WebSocket 服务。

## macOS 安装

### 一键安装（推荐）

终端中执行：

```bash
curl -fsSL https://raw.githubusercontent.com/sleepfin/wizclaw/main/scripts/install-wizclaw.sh | bash
```

脚本会自动检测架构（Intel x64 / Apple Silicon arm64），下载对应的最新 release 到 `~/.local/bin` 并添加到 PATH。

> **Gatekeeper 提示**：安装脚本已自动处理。如手动下载，需运行 `xattr -d com.apple.quarantine wizclaw` 解除隔离。

### 手动安装

1. 前往 [Releases](https://github.com/sleepfin/wizclaw/releases) 下载对应架构的文件：
   - Apple Silicon (M1/M2/M3/M4): `wizclaw-macos-arm64`
   - Intel Mac: `wizclaw-macos-x64`
2. 重命名为 `wizclaw`，放到 PATH 中任意目录
3. 赋予执行权限：`chmod +x wizclaw`
4. 解除 Gatekeeper 隔离：`xattr -d com.apple.quarantine wizclaw`

### 本地构建

需要 Python 3.12+：

```bash
./scripts/build-wizclaw.sh
```

产物在 `dist/wizclaw-macos-arm64` 或 `dist/wizclaw-macos-x64`（取决于你的机器架构）。

## Linux 安装

### 一键安装（推荐）

```bash
curl -fsSL https://raw.githubusercontent.com/sleepfin/wizclaw/main/scripts/install-wizclaw.sh | bash
```

脚本会自动检测架构，下载最新 release 到 `~/.local/bin` 并添加到 PATH。

### 手动安装

1. 前往 [Releases](https://github.com/sleepfin/wizclaw/releases) 下载 `wizclaw-linux-x64`
2. 重命名为 `wizclaw`，放到 PATH 中任意目录
3. 赋予执行权限：`chmod +x wizclaw`

### 本地构建

需要 Python 3.12+：

```bash
./scripts/build-wizclaw.sh
```

## Windows 安装

### 一键安装（推荐）

PowerShell 中执行：

```powershell
iwr -useb https://raw.githubusercontent.com/sleepfin/wizclaw/main/scripts/install-wizclaw.ps1 | iex
```

脚本会自动下载最新 release 的 `wizclaw.exe` 到 `%USERPROFILE%\.local\bin` 并添加到用户 PATH。安装后重启终端即可使用。

### 手动安装

1. 前往 [Releases](https://github.com/sleepfin/wizclaw/releases) 下载 `wizclaw-windows-x64.exe`
2. 重命名为 `wizclaw.exe`，放到 PATH 中任意目录

### 本地构建

需要 Python 3.12+：

```powershell
.\scripts\build-wizclaw.ps1
```

产物在 `dist/wizclaw-windows-x64.exe`。

## 使用

```bash
wizclaw              # 首次运行自动进入配置向导，然后启动
wizclaw config       # 重新配置
wizclaw config --force  # 强制覆盖已有配置
wizclaw version      # 查看版本
```

配置文件位置：`%APPDATA%\wizclaw\config.yaml`（Windows）或 `~/.wizclaw/config.yaml`（macOS / Linux）。

## 发版流程

代码更新后，打 tag 推送即可触发 GitHub Actions 自动构建并创建 Release。

### 1. 更新版本号

编辑 `bridge/__init__.py`：

```python
__version__ = "0.2.0"  # 改成新版本
```

### 2. 提交代码

```bash
git add -A
git commit -m "feat: 你的改动描述"
```

### 3. 打 tag 并推送

```bash
git tag v0.2.0
git push origin main --tags
```

tag 必须以 `v` 开头（如 `v0.2.0`），推送后 GitHub Actions 会自动：

1. 在 `windows-latest` 上构建 `wizclaw-windows-x64.exe`
2. 在 `macos-latest` (Apple Silicon) 上构建 `wizclaw-macos-arm64`
3. 在 `macos-15-intel` (Intel) 上构建 `wizclaw-macos-x64`
4. 在 `ubuntu-latest` 上构建 `wizclaw-linux-x64`
5. 创建 GitHub Release，附带所有平台的二进制文件

### 手动触发构建（不发 Release）

在 GitHub 仓库页面 → Actions → Build wizclaw → Run workflow，可以手动触发构建。此方式只上传 artifact，不会创建 Release。
