# DocHistory 打包说明

## Windows 环境打包（生成 .exe 文件）

### 方法一：使用打包脚本（推荐）

1. 在Windows上克隆仓库：
```cmd
git clone https://github.com/mimi202605/Document-History.git
cd Document-History
```

2. 双击运行 `build.bat` 脚本，或命令行执行：
```cmd
build.bat
```

3. 打包完成后，在 `dist\` 目录下找到 `DocHistory.exe`

### 方法二：手动打包

1. 安装依赖：
```cmd
pip install -r requirements.txt
pip install pyinstaller
```

2. 执行打包命令：
```cmd
pyinstaller DocHistory.spec --clean --noconfirm
```

3. 生成的exe文件位于 `dist\DocHistory.exe`

## 使用方法

双击 `DocHistory.exe` 即可启动应用：
- 应用启动后会显示主窗口和系统托盘图标
- 在设置中添加需要监控的文件夹
- 编辑 .docx 文件时会自动记录版本
- 可随时回退、比较差异、导出版本

## 技术说明

- **打包工具**：PyInstaller 6.21+
- **单文件模式**：所有依赖打包进单个exe文件
- **无控制台窗口**：GUI应用，后台运行
- **跨平台**：spec文件支持Windows/Linux/macOS

## 注意事项

- exe文件体积约80MB（包含PyQt6和所有依赖）
- 首次启动可能稍慢（解压临时文件）
- Windows Defender可能误报，需添加信任
- 如需自定义图标，在spec文件中取消icon行注释并提供.ico文件
