# Novel

桌面写作程序。窗口由 Qt 绘制。注册和登录在本机完成，正文、设定、对话和模型密钥都留在这台电脑上。

## 运行

需要 Python 3.10 或更新版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m desktop
```

打开就是登录或注册。程序会自己把账号服务带起来，界面上不需要填写地址。模型地址、模型名和密钥在书架的「模型」里填写，请求直接发到供应商。

书库在 `%APPDATA%\Novel\users\<用户 id>\library.sqlite`。

## 测试

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -t .
```

## 安装包

`packaging\build.ps1` 会下载嵌入式 Python，装上 `requirements.txt` 里的依赖，并把程序、样式表、图标和提示词放进 `dist\Novel`。装了 Inno Setup 6 时，脚本会继续编出 `dist\Novel-Setup.exe`。安装不需要管理员权限，目录在本机的 `%LOCALAPPDATA%\Novel`。
