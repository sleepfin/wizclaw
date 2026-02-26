# wizclaw

Bridge daemon，将本地 OpenClaw agent 连接到云端 WebSocket 服务。

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

配置文件位置：`%APPDATA%\wizclaw\config.yaml`（Windows）或 `~/.wizclaw/config.yaml`（Linux/macOS）。

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

1. 在 `windows-latest` runner 上用 PyInstaller 构建 `wizclaw.exe`
2. 创建 GitHub Release，附带 `wizclaw-windows-x64.exe`

### 手动触发构建（不发 Release）

在 GitHub 仓库页面 → Actions → Build wizclaw → Run workflow，可以手动触发构建。此方式只上传 artifact，不会创建 Release。
