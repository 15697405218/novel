# Novel

桌面写作程序。窗口由 Qt 绘制。账号服务只负责注册、登录和校验登录态，正文、设定、对话和模型密钥都留在本机。

## 运行

需要 Python 3.10 或更新版本。

```powershell
cd D:\agent____\novel-agent\novel
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m auth
```

另开一个窗口：

```powershell
.\.venv\Scripts\python -m desktop
```

打开就是登录或注册。账号服务默认在 `http://127.0.0.1:8787`，登录页可以改地址。模型地址、模型名和密钥在书架的「模型」里填写，请求直接发到供应商，不经过账号服务。

书库在 `%APPDATA%\Novel\users\<用户 id>\library.sqlite`。

## 测试

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -t .
```

## 安装包

`packaging\build.ps1` 用 PyInstaller 打出目录，再用 Inno Setup 编译 `packaging\novel.iss`。
