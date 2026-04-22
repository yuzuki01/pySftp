#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
import stat
import paramiko
from datetime import datetime
import json


def get_config_dir():
    """获取用户配置目录"""
    config_dir = os.path.join(os.path.expanduser("~"), ".pysftp")
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir)
        except Exception as e:
            print(f"无法创建配置目录: {e}")
            return None
    return config_dir


def get_favorites_file():
    """获取收藏文件路径"""
    config_dir = get_config_dir()
    if config_dir:
        return os.path.join(config_dir, "favorites.json")
    return None


def load_favorites():
    """加载收藏的主机信息"""
    favorites_file = get_favorites_file()
    if favorites_file and os.path.exists(favorites_file):
        try:
            with open(favorites_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"无法加载收藏数据: {e}")
    return []


def save_favorites(favorites):
    """保存收藏的主机信息"""
    favorites_file = get_favorites_file()
    if favorites_file:
        try:
            with open(favorites_file, "w", encoding="utf-8") as f:
                json.dump(favorites, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"无法保存收藏数据: {e}")
    return False


def format_file_size(size_bytes):
    """格式化文件大小，添加适当的单位"""
    if size_bytes == 0:
        return "0 bytes"
    units = ["bytes", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    return f"{size:.1f} {units[unit_index]}"


class SFTPClient:
    def __init__(self, root):
        self.root = root
        self.root.title("SFTP 文件传输客户端")
        self.root.geometry("1000x700")

        self.ssh_client = None
        self.sftp = None
        self.current_remote_path = "/"
        self.remote_home_path = None
        self.current_local_path = os.path.expanduser("~")

        self.setup_ui()

    def setup_ui(self):
        # 连接框架
        conn_frame = ttk.LabelFrame(self.root, text="SFTP 连接", padding=10)
        conn_frame.pack(fill=tk.X, padx=10, pady=5)

        # 主机
        ttk.Label(conn_frame, text="主机:").grid(row=0, column=0, padx=5, pady=5)
        # 主机地址选择框
        self.host_var = tk.StringVar()
        self.host_combobox = ttk.Combobox(conn_frame, textvariable=self.host_var, width=28)
        self.host_combobox.grid(row=0, column=1, padx=5, pady=5)
        # 加载收藏的主机地址
        self.load_favorites_to_combobox()
        # 绑定选择事件
        self.host_combobox.bind("<<ComboboxSelected>>", self.on_host_selected)
        # 默认值
        self.host_combobox.set("localhost")

        # 端口
        ttk.Label(conn_frame, text="端口:").grid(row=0, column=2, padx=5, pady=5)
        self.port_entry = ttk.Entry(conn_frame, width=8)
        self.port_entry.grid(row=0, column=3, padx=5, pady=5)
        self.port_entry.insert(0, "22")

        # 用户名
        ttk.Label(conn_frame, text="用户名:").grid(row=0, column=4, padx=5, pady=5)
        self.username_entry = ttk.Entry(conn_frame, width=15)
        self.username_entry.grid(row=0, column=5, padx=5, pady=5)

        # 密码
        ttk.Label(conn_frame, text="密码:").grid(row=1, column=0, padx=5, pady=5)
        self.password_entry = ttk.Entry(conn_frame, width=30, show="*")
        self.password_entry.grid(row=1, column=1, padx=5, pady=5)

        # 密钥文件
        ttk.Label(conn_frame, text="密钥文件:").grid(row=1, column=2, padx=5, pady=5)
        self.key_entry = ttk.Entry(conn_frame, width=20)
        self.key_entry.grid(row=1, column=3, columnspan=2, padx=5, pady=5)
        ttk.Button(conn_frame, text="浏览...", command=self.browse_key).grid(row=1, column=5, padx=5, pady=5)

        # 连接按钮
        self.connect_btn = ttk.Button(conn_frame, text="连接", command=self.connect_sftp)
        self.connect_btn.grid(row=0, column=6, padx=10, pady=5)
        # 收藏按钮
        self.favorite_btn = ttk.Button(conn_frame, text="☆", style="Favorite.TButton", command=self.toggle_favorite)
        self.favorite_btn.grid(row=1, column=8, padx=5, pady=5)
        # 初始化按钮状态
        self.is_favorite = False
        self.favorite_btn.config(state=tk.DISABLED)
        ttk.Button(conn_frame, text="断开", command=self.disconnect_sftp).grid(row=0, column=8, padx=5, pady=5)

        # 状态标签
        self.status_label = ttk.Label(conn_frame, text="未连接", foreground="red")
        self.status_label.grid(row=2, column=0, columnspan=8, pady=5)

        # 主内容区 - 分隔为本地和远程
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 本地文件框架
        local_frame = ttk.LabelFrame(main_paned, text="本地文件", padding=10)
        main_paned.add(local_frame, weight=1)

        # 本地路径
        local_path_frame = ttk.Frame(local_frame)
        local_path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(local_path_frame, text="路径:").pack(side=tk.LEFT)
        self.local_path_var = tk.StringVar()
        self.local_path_entry = ttk.Entry(local_path_frame, textvariable=self.local_path_var)
        self.local_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.local_path_entry.bind("<Return>", lambda e: self.refresh_local())
        ttk.Button(local_path_frame, text="浏览...", command=self.browse_local_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(local_path_frame, text="刷新", command=self.refresh_local).pack(side=tk.LEFT, padx=5)

        # 本地文件列表
        local_tree_frame = ttk.Frame(local_frame)
        local_tree_frame.pack(fill=tk.BOTH, expand=True)

        self.local_tree = ttk.Treeview(local_tree_frame, columns=("name", "size", "modified"), show="headings")
        self.local_tree.heading("name", text="名称")
        self.local_tree.heading("size", text="大小")
        self.local_tree.heading("modified", text="修改时间")
        self.local_tree.column("name", width=200)
        self.local_tree.column("size", width=100)
        self.local_tree.column("modified", width=150)
        self.local_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        local_scroll = ttk.Scrollbar(local_tree_frame, orient=tk.VERTICAL, command=self.local_tree.yview)
        self.local_tree.configure(yscrollcommand=local_scroll.set)
        local_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.local_tree.bind("<Double-1>", self.on_local_double_click)

        # 远程文件框架
        remote_frame = ttk.LabelFrame(main_paned, text="远程文件 (SFTP)", padding=10)
        main_paned.add(remote_frame, weight=1)

        # 远程路径
        remote_path_frame = ttk.Frame(remote_frame)
        remote_path_frame.pack(fill=tk.X, pady=5)
        ttk.Label(remote_path_frame, text="路径:").pack(side=tk.LEFT)
        # Back 按钮
        self.back_btn = ttk.Button(remote_path_frame, text="←", width=4, command=self.remote_go_back)
        self.back_btn.pack(side=tk.LEFT, padx=2)
        # Home 按钮
        self.home_btn = ttk.Button(remote_path_frame, text="~", width=4, command=self.remote_go_home)
        self.home_btn.pack(side=tk.LEFT, padx=2)
        self.remote_path_var = tk.StringVar()
        self.remote_path_entry = ttk.Entry(remote_path_frame, textvariable=self.remote_path_var)
        self.remote_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.remote_path_entry.bind("<Return>", lambda e: self.refresh_remote())
        ttk.Button(remote_path_frame, text="刷新", command=self.refresh_remote).pack(side=tk.LEFT, padx=5)

        # 远程文件列表
        remote_tree_frame = ttk.Frame(remote_frame)
        remote_tree_frame.pack(fill=tk.BOTH, expand=True)

        self.remote_tree = ttk.Treeview(remote_tree_frame, columns=("name", "size", "modified"), show="headings")
        self.remote_tree.heading("name", text="名称")
        self.remote_tree.heading("size", text="大小")
        self.remote_tree.heading("modified", text="修改时间")
        self.remote_tree.column("name", width=200)
        self.remote_tree.column("size", width=100)
        self.remote_tree.column("modified", width=150)
        self.remote_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        remote_scroll = ttk.Scrollbar(remote_tree_frame, orient=tk.VERTICAL, command=self.remote_tree.yview)
        self.remote_tree.configure(yscrollcommand=remote_scroll.set)
        remote_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.remote_tree.bind("<Double-1>", self.on_remote_double_click)

        # 传输按钮区
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="上传 →", command=self.upload_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="← 下载", command=self.download_files).pack(side=tk.LEFT, padx=5)

        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(btn_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=20)

        # 初始化本地文件列表
        self.refresh_local()

    def browse_key(self):
        filename = filedialog.askopenfilename(title="选择密钥文件")
        if filename:
            self.key_entry.delete(0, tk.END)
            self.key_entry.insert(0, filename)

    def browse_local_directory(self):
        directory = filedialog.askdirectory(
            title="选择本地文件夹",
            initialdir=self.current_local_path
        )
        if directory:
            self.local_path_var.set(directory)
            self.refresh_local()

    def remote_go_back(self):
        if not self.sftp:
            return
        if self.current_remote_path != "/":
            new_path = os.path.dirname(self.current_remote_path)
            self.remote_path_var.set(new_path)
            self.refresh_remote()

    def remote_go_home(self):
        if not self.sftp or not self.remote_home_path:
            return
        self.remote_path_var.set(self.remote_home_path)
        self.refresh_remote()

    def connect_sftp(self):
        host = self.host_combobox.get()
        port = int(self.port_entry.get())
        username = self.username_entry.get()
        password = self.password_entry.get()
        key_file = self.key_entry.get()

        def connect_thread():
            try:
                self.status_label.config(text="正在连接...", foreground="orange")
                self.connect_btn.config(state=tk.DISABLED)

                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

                if key_file:
                    private_key = paramiko.RSAKey.from_private_key_file(key_file)
                    self.ssh_client.connect(host, port, username, pkey=private_key)
                else:
                    self.ssh_client.connect(host, port, username, password)

                self.sftp = self.ssh_client.open_sftp()
                # 获取用户主目录
                try:
                    stdin, stdout, stderr = self.ssh_client.exec_command("echo $HOME")
                    home_path = stdout.read().decode().strip()
                    if home_path:
                        self.remote_home_path = home_path
                    else:
                        self.remote_home_path = f"/home/{username}"
                except:
                    self.remote_home_path = f"/home/{username}"
                self.current_remote_path = self.remote_home_path

                self.root.after(0, lambda: self.status_label.config(text=f"已连接到 {host}", foreground="green"))
                self.root.after(0, self.refresh_remote)
                # 启用收藏按钮并检查是否已收藏
                self.root.after(0, lambda: self.favorite_btn.config(state=tk.NORMAL))
                self.root.after(0, self.check_if_favorite)

            except Exception as e:
                self.root.after(0, lambda: self.status_label.config(text=f"连接失败: {str(e)}", foreground="red"))
                messagebox.showerror("连接错误", str(e))
            finally:
                self.root.after(0, lambda: self.connect_btn.config(state=tk.NORMAL))

        threading.Thread(target=connect_thread, daemon=True).start()

    def disconnect_sftp(self):
        if self.sftp:
            self.sftp.close()
            self.sftp = None
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
        self.status_label.config(text="未连接", foreground="red")
        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)
        # 禁用收藏按钮
        self.favorite_btn.config(state=tk.DISABLED, text="☆")
        self.is_favorite = False

    def load_favorites_to_combobox(self):
        """加载收藏的主机地址到下拉菜单"""
        favorites = load_favorites()
        if favorites:
            # 格式化显示为 "{username}@{ip}:{port}"
            host_list = [f"{fav['username']}@{fav['ip']}:{fav.get('port', 22)}" for fav in favorites]
            self.host_combobox["values"] = host_list
        else:
            # 收藏列表为空时，清空下拉菜单内容
            self.host_combobox["values"] = []
        # 强制刷新 Combobox 显示
        self.host_combobox.update()

    def on_host_selected(self, event):
        """当选择主机地址时自动填充用户名和端口"""
        selected_text = self.host_combobox.get()
        # 从格式化为 "username@ip:port" 的字符串中提取信息
        if "@" in selected_text and ":" in selected_text:
            username, rest = selected_text.split("@", 1)
            ip, port = rest.split(":", 1)

            # 更新各个输入字段
            self.host_combobox.set(ip)
            self.username_entry.delete(0, tk.END)
            self.username_entry.insert(0, username)
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, port)
        elif "@" in selected_text:
            # 如果只有 username@ip 格式
            username, ip = selected_text.split("@", 1)
            self.host_combobox.set(ip)
            self.username_entry.delete(0, tk.END)
            self.username_entry.insert(0, username)
        elif ":" in selected_text:
            # 如果只有 ip:port 格式
            ip, port = selected_text.split(":", 1)
            self.host_combobox.set(ip)
            self.port_entry.delete(0, tk.END)
            self.port_entry.insert(0, port)

    def toggle_favorite(self):
        """切换收藏状态"""
        if not self.sftp:
            return

        current_ip = self.host_combobox.get()
        current_username = self.username_entry.get()

        favorites = load_favorites()

        if self.is_favorite:
            # 取消收藏
            current_port = int(self.port_entry.get())
            favorites = [fav for fav in favorites if not (fav["ip"] == current_ip and fav["username"] == current_username and fav.get("port", 22) == current_port)]
            self.favorite_btn.config(text="☆")
            self.is_favorite = False
        else:
            # 添加收藏
            favorite = {"ip": current_ip, "username": current_username, "port": int(self.port_entry.get())}
            # 检查是否已存在相同的收藏项（包含 IP、用户名和端口）
            exists = False
            for fav in favorites:
                if fav["ip"] == current_ip and fav["username"] == current_username and fav["port"] == int(self.port_entry.get()):
                    exists = True
                    break
            if not exists:
                favorites.append(favorite)
                self.favorite_btn.config(text="★")
                self.is_favorite = True

        save_favorites(favorites)
        # 更新下拉菜单
        self.load_favorites_to_combobox()

    def check_if_favorite(self):
        """检查当前连接的主机是否已收藏"""
        if not self.sftp:
            return False

        current_ip = self.host_combobox.get()
        current_username = self.username_entry.get()
        current_port = int(self.port_entry.get())

        favorites = load_favorites()

        # 初始状态设置为未收藏
        self.favorite_btn.config(text="☆")
        self.is_favorite = False

        for fav in favorites:
            if fav["ip"] == current_ip and fav["username"] == current_username and fav.get("port", 22) == current_port:
                self.favorite_btn.config(text="★")
                self.is_favorite = True
                break

        return self.is_favorite

    def refresh_local(self):
        path = self.local_path_var.get() or self.current_local_path
        if not os.path.exists(path):
            path = os.path.expanduser("~")

        self.current_local_path = path
        self.local_path_var.set(path)

        for item in self.local_tree.get_children():
            self.local_tree.delete(item)

        if path != os.path.dirname(path):
            self.local_tree.insert("", tk.END, values=("..", "", ""))

        try:
            items = os.listdir(path)
            # 先收集所有文件信息
            file_list = []
            for item in items:
                item_path = os.path.join(path, item)
                is_link = os.path.islink(item_path)
                is_dir = os.path.isdir(item_path)
                file_list.append((item, is_link, is_dir))

            # 排序规则：第一级是软链接或目录(0)，第二级是文件(1)，每级内按文件名排序
            for item, is_link, is_dir in sorted(file_list, key=lambda x: (0 if (x[1] or x[2]) else 1, x[0])):
                item_path = os.path.join(path, item)
                link_target = ""
                if is_link:
                    try:
                        link_target = os.readlink(item_path)
                    except:
                        pass
                stat_info = os.lstat(item_path) if is_link else os.stat(item_path)
                size = stat_info.st_size if not is_dir else ""
                modified = datetime.fromtimestamp(stat_info.st_mtime).strftime("%Y-%m-%d %H:%M")

                if is_link:
                    if link_target:
                        name = f"🔗 {item} -> {link_target}"
                    else:
                        name = f"🔗 {item}"
                    formatted_size = "<link>"
                elif is_dir:
                    name = f"📁 {item}"
                    formatted_size = "<dir>"
                else:
                    name = item
                    formatted_size = format_file_size(size)
                self.local_tree.insert("", tk.END, values=(name, formatted_size, modified))
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def refresh_remote(self):
        if not self.sftp:
            return

        path = self.remote_path_var.get() or self.current_remote_path

        try:
            self.sftp.chdir(path)
            self.current_remote_path = path
        except:
            path = self.current_remote_path

        self.remote_path_var.set(path)

        for item in self.remote_tree.get_children():
            self.remote_tree.delete(item)

        if path != "/":
            self.remote_tree.insert("", tk.END, values=("..", "", ""))

        try:
            items = self.sftp.listdir_attr(path)
            # 排序规则：第一级是软链接或目录(0)，第二级是文件(1)，每级内按文件名排序
            for item in sorted(items, key=lambda x: (0 if (stat.S_ISLNK(x.st_mode) or stat.S_ISDIR(x.st_mode)) else 1, x.filename)):
                is_link = stat.S_ISLNK(item.st_mode)
                is_dir = stat.S_ISDIR(item.st_mode)
                size = item.st_size if not is_dir else ""
                modified = datetime.fromtimestamp(item.st_mtime).strftime("%Y-%m-%d %H:%M")

                if is_link:
                    # 尝试读取软链接目标
                    link_target = ""
                    try:
                        link_path = os.path.join(path, item.filename).replace("\\", "/")
                        link_target = self.sftp.readlink(link_path)
                    except:
                        pass
                    if link_target:
                        name = f"🔗 {item.filename} -> {link_target}"
                    else:
                        name = f"🔗 {item.filename}"
                    formatted_size = "<link>"
                elif is_dir:
                    name = f"📁 {item.filename}"
                    formatted_size = "<dir>"
                else:
                    name = item.filename
                    formatted_size = format_file_size(size)
                self.remote_tree.insert("", tk.END, values=(name, formatted_size, modified))
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def on_local_double_click(self, event):
        selection = self.local_tree.selection()
        if not selection:
            return

        item = self.local_tree.item(selection[0])
        name = item["values"][0]

        if name == "..":
            new_path = os.path.dirname(self.current_local_path)
            self.local_path_var.set(new_path)
            self.refresh_local()
        elif name.startswith("📁 "):
            dir_name = name[2:]
            new_path = os.path.join(self.current_local_path, dir_name)
            self.local_path_var.set(new_path)
            self.refresh_local()
        elif name.startswith("🔗 "):
            # 提取软链接名称（去掉 🔗 和 -> 后面的内容）
            link_name = name[2:].split(" -> ")[0]
            link_path = os.path.join(self.current_local_path, link_name)
            if os.path.isdir(link_path):
                self.local_path_var.set(link_path)
                self.refresh_local()

    def on_remote_double_click(self, event):
        if not self.sftp:
            return

        selection = self.remote_tree.selection()
        if not selection:
            return

        item = self.remote_tree.item(selection[0])
        name = item["values"][0]

        if name == "..":
            new_path = os.path.dirname(self.current_remote_path)
            self.remote_path_var.set(new_path)
            self.refresh_remote()
        elif name.startswith("📁 "):
            dir_name = name[2:]
            new_path = os.path.join(self.current_remote_path, dir_name).replace("\\", "/")
            self.remote_path_var.set(new_path)
            self.refresh_remote()
        elif name.startswith("🔗 "):
            # 提取软链接名称（去掉 🔗 和 -> 后面的内容）
            link_name = name[2:].split(" -> ")[0]
            link_path = os.path.join(self.current_remote_path, link_name).replace("\\", "/")
            # 尝试判断链接指向的是否为目录
            try:
                # 使用 stat 判断链接目标是否为目录
                st = self.sftp.stat(link_path)
                if stat.S_ISDIR(st.st_mode):
                    self.remote_path_var.set(link_path)
                    self.refresh_remote()
            except:
                pass

    def upload_directory(self, local_dir, remote_dir, progress_callback):
        """递归上传目录"""
        try:
            self.sftp.mkdir(remote_dir)
        except IOError:
            pass  # 目录可能已存在

        for item in os.listdir(local_dir):
            local_path = os.path.join(local_dir, item)
            remote_path = os.path.join(remote_dir, item).replace("\\", "/")

            if os.path.islink(local_path):
                # 处理软链接
                link_target = os.readlink(local_path)
                try:
                    self.sftp.symlink(link_target, remote_path)
                except:
                    real_path = os.path.join(os.path.dirname(local_path), link_target)
                    if os.path.exists(real_path) and not os.path.isdir(real_path):
                        self.sftp.put(real_path, remote_path, callback=progress_callback)
            elif os.path.isdir(local_path):
                # 递归上传子目录
                self.upload_directory(local_path, remote_path, progress_callback)
            else:
                # 上传文件
                self.sftp.put(local_path, remote_path, callback=progress_callback)

    def upload_files(self):
        if not self.sftp:
            messagebox.showwarning("警告", "请先连接到 SFTP 服务器")
            return

        selection = self.local_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要上传的文件")
            return

        def progress_callback(transferred, total):
            percent = (transferred / total) * 100
            self.progress_var.set(percent)
            self.root.update_idletasks()

        def upload_thread():
            try:
                for sel in selection:
                    item = self.local_tree.item(sel)
                    name = item["values"][0]
                    if name == "..":
                        continue

                    # 提取真实名称
                    if name.startswith("📁 "):
                        filename = name[2:]
                    elif name.startswith("🔗 "):
                        filename = name[2:].split(" -> ")[0]
                    else:
                        filename = name

                    local_path = os.path.join(self.current_local_path, filename)
                    remote_path = os.path.join(self.current_remote_path, filename).replace("\\", "/")

                    if os.path.isdir(local_path) and not os.path.islink(local_path):
                        # 上传目录
                        self.upload_directory(local_path, remote_path, progress_callback)
                    elif os.path.islink(local_path):
                        # 上传软链接
                        link_target = os.readlink(local_path)
                        try:
                            self.sftp.symlink(link_target, remote_path)
                        except Exception as e:
                            real_path = os.path.join(os.path.dirname(local_path), link_target)
                            if os.path.exists(real_path) and not os.path.isdir(real_path):
                                self.sftp.put(real_path, remote_path, callback=progress_callback)
                            else:
                                raise
                    else:
                        # 上传文件
                        self.sftp.put(local_path, remote_path, callback=progress_callback)

                self.root.after(0, lambda: messagebox.showinfo("成功", "上传完成"))
                self.root.after(0, self.refresh_remote)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.progress_var.set(0)

        threading.Thread(target=upload_thread, daemon=True).start()

    def download_directory(self, remote_dir, local_dir, progress_callback):
        """递归下载目录"""
        if not os.path.exists(local_dir):
            os.makedirs(local_dir)

        for item in self.sftp.listdir_attr(remote_dir):
            remote_path = os.path.join(remote_dir, item.filename).replace("\\", "/")
            local_path = os.path.join(local_dir, item.filename)

            if stat.S_ISLNK(item.st_mode):
                # 处理软链接
                link_target = self.sftp.readlink(remote_path)
                try:
                    if os.name == 'posix':
                        os.symlink(link_target, local_path)
                    else:
                        self.sftp.get(remote_path, local_path, callback=progress_callback)
                except OSError:
                    self.sftp.get(remote_path, local_path, callback=progress_callback)
            elif stat.S_ISDIR(item.st_mode):
                # 递归下载子目录
                self.download_directory(remote_path, local_path, progress_callback)
            else:
                # 下载文件
                self.sftp.get(remote_path, local_path, callback=progress_callback)

    def download_files(self):
        if not self.sftp:
            messagebox.showwarning("警告", "请先连接到 SFTP 服务器")
            return

        selection = self.remote_tree.selection()
        if not selection:
            messagebox.showwarning("警告", "请选择要下载的文件")
            return

        def progress_callback(transferred, total):
            percent = (transferred / total) * 100
            self.progress_var.set(percent)
            self.root.update_idletasks()

        def download_thread():
            try:
                for sel in selection:
                    item = self.remote_tree.item(sel)
                    name = item["values"][0]
                    if name == "..":
                        continue

                    # 提取真实名称
                    if name.startswith("📁 "):
                        filename = name[2:]
                    elif name.startswith("🔗 "):
                        filename = name[2:].split(" -> ")[0]
                    else:
                        filename = name

                    remote_path = os.path.join(self.current_remote_path, filename).replace("\\", "/")
                    local_path = os.path.join(self.current_local_path, filename)

                    # 检查文件类型
                    st = self.sftp.lstat(remote_path)
                    if stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                        # 下载目录
                        self.download_directory(remote_path, local_path, progress_callback)
                    elif stat.S_ISLNK(st.st_mode):
                        # 下载软链接
                        link_target = self.sftp.readlink(remote_path)
                        try:
                            if os.name == 'posix':
                                os.symlink(link_target, local_path)
                            else:
                                self.sftp.get(remote_path, local_path, callback=progress_callback)
                        except OSError:
                            self.sftp.get(remote_path, local_path, callback=progress_callback)
                    else:
                        # 下载文件
                        self.sftp.get(remote_path, local_path, callback=progress_callback)

                self.root.after(0, lambda: messagebox.showinfo("成功", "下载完成"))
                self.root.after(0, self.refresh_local)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", str(e)))
            finally:
                self.progress_var.set(0)

        threading.Thread(target=download_thread, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = SFTPClient(root)
    root.mainloop()
