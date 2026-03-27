# SFTP 文件传输客户端

一个基于 Python 的图形化 SFTP 文件传输工具，支持本地/远程文件浏览和双向文件传输。

## 功能特性

- 支持密码或 SSH 密钥认证
- 双面板界面：本地文件 + 远程 SFTP 文件
- 目录浏览：双击进入文件夹，支持返回上级
- 文件传输：上传/下载，带进度条显示
- 快捷导航：Back 返回上级、Home 回到用户主目录
- Windows 原生文件夹选择器支持

## 依赖安装

### Windows 10

1. 确保已安装 Python 3.7+
2. 打开命令提示符 (CMD) 或 PowerShell
3. 运行以下命令安装依赖：

```cmd
pip install -r requirements.txt
```

或者单独安装：

```cmd
pip install paramiko>=3.0.0
```

### Ubuntu / Debian

1. 确保已安装 Python 3.7+ 和 pip：

```bash
sudo apt update
sudo apt install python3 python3-pip python3-tk -y
```

2. 安装依赖：

```bash
pip3 install -r requirements.txt
```

或者单独安装：

```bash
pip3 install paramiko>=3.0.0
```

### CentOS / RHEL

```bash
sudo yum install python3 python3-pip python3-tkinter -y
pip3 install paramiko>=3.0.0
```

### macOS

```bash
brew install python3
pip3 install paramiko>=3.0.0
```

## 运行方式

```bash
python sftp_client.py
```

或在 Linux/macOS 上：

```bash
python3 sftp_client.py
```

## 使用说明

1. 填写 SFTP 连接信息（主机、端口、用户名、密码/密钥文件）
2. 点击"连接"按钮建立连接
3. 在左侧本地文件面板选择文件，点击"上传 →"上传到远程
4. 在右侧远程文件面板选择文件，点击"← 下载"下载到本地

## 界面说明

- **本地文件**：左侧面板显示本地文件系统
- **远程文件**：右侧面板显示 SFTP 服务器文件
- **← 按钮**：返回上一级目录
- **~ 按钮**：回到用户主目录
- **浏览...**：打开 Windows 文件夹选择器

## 项目文件

```
pySftp/
├── sftp_client.py    # 主程序文件
├── requirements.txt   # 依赖列表
└── README.md          # 本文件
```
