# DocHistory - 本地文档版本控制系统 设计文档

**版本**：v1.0 (MVP)
**日期**：2026-06-12
**目标平台**：Linux 开发验证 → Windows 生产部署
**开发模式**：Vibe Coding（先跑通核心流程，再逐步优化）

## 一、MVP 范围

### 包含
- 监控 `.docx` 文件（`.doc`/`.wps` 的 COM 部分留 Windows 补全，代码预留接口）
- 完整快照存储（zlib 压缩）
- GitHub Desktop 风格 GUI（左文件列表 + 右版本时间线）
- 完整系统托盘（最小化常驻、右键菜单控制监控）
- 文本行级 diff 差异比较（difflib + 行级颜色高亮）
- 版本回退 + 导出任意版本
- 自动清理（按保留天数/最大版本数）
- 手动创建带备注版本

### 排除（留后续迭代）
- doc/wps 文件的 COM 解析（Windows 阶段补全）
- 增量 delta 存储（完整快照已满足 MVP）
- 文件重命名/移动跟踪
- 版本标签功能
- 批量导出
- 深色模式（MVP 固定深色主题）
- 云同步、团队协作

## 二、技术栈

| 功能模块 | 库 | 版本 | 备注 |
|---------|-----|------|-----|
| 文件系统监控 | watchdog | 4.0.1+ | 跨平台递归监控 |
| DOCX 解析 | python-docx | 1.1.2+ | 纯 Python，无需 Office |
| DOC/WPS 解析 | pywin32 | 306+ | Windows 专用，Linux 留空壳 |
| 桌面 GUI | PyQt6 | 6.7.0+ | 方案 B 布局 |
| 版本差异 | difflib | 内置 | 文本行级 diff |
| 数据存储 | sqlite3 | 内置 | 单文件数据库 |
| 文件压缩 | zlib | 内置 | 压缩版本快照 |
| 打包 | PyInstaller | 最新 | 单 exe 分发 |
| 测试 | pytest | 8.0+ | 单元 + 集成测试 |

**运行环境**：Python 3.14（开发环境），目标兼容 3.10+（Windows 部署）

## 三、架构设计

### 模块结构
```
dochistory/
├── main.py                 # 程序入口
├── core/
│   ├── __init__.py
│   ├── database.py         # SQLite 封装，所有 SQL 集中于此
│   ├── file_monitor.py     # watchdog 监控 + 防抖，发出"文件已保存"信号
│   ├── document_parser.py  # 解析器基类 + DocxParser 实现
│   └── version_manager.py  # 版本创建/查询/回退/清理业务逻辑
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # 主窗口（方案 B 布局）
│   ├── diff_window.py      # 差异比较窗口
│   ├── settings_window.py  # 设置窗口
│   └── tray.py             # 系统托盘
├── utils/
│   ├── __init__.py
│   ├── file_utils.py       # 哈希、压缩、路径工具
│   └── diff_utils.py       # difflib 封装
└── resources/
    └── icons/              # 图标资源
```

### 模块职责

每个模块单一职责、可独立测试：

- **database.py** — SQLite 封装，所有 SQL 集中于此。对外暴露 `Database` 类，方法包括 `add_folder`、`get_files`、`create_version`、`get_versions`、`rollback_version` 等。内部用 `threading.Lock` 保证线程安全。
- **file_monitor.py** — 基于 watchdog 的 Observer 模式。监听 `on_modified`，500ms 防抖，过滤临时文件和扩展名。通过 Qt 信号（跨线程安全）通知 UI，不直接操作 widget。
- **document_parser.py** — 抽象基类 `BaseDocumentParser`，定义 `extract_text() -> str` 和 `save_version(file_path, version_path) -> bool` 接口。`DocxParser` 用 python-docx 实现。`Win32DocumentParser` 留空壳，Linux 上调用抛 `NotImplementedError`。
- **version_manager.py** — 核心业务逻辑。版本创建（哈希去重）、查询、回退（原子替换）、自动清理。协调 database、document_parser、file_utils。
- **main_window.py** — 方案 B 布局：顶部文件夹下拉 + 搜索框，左侧文件列表，右侧版本时间线 + 操作按钮。
- **diff_window.py** — 左右分栏显示两个版本文本，新增绿、删除红、修改黄。
- **tray.py** — 系统托盘图标 + 右键菜单（暂停/恢复监控、打开主窗口、退出）。关闭窗口最小化到托盘。
- **file_utils.py** — MD5 哈希、zlib 压缩/解压、临时文件过滤、跨平台数据目录定位。
- **diff_utils.py** — difflib 封装，返回结构化差异（新增/删除/修改行分类）。

## 四、数据流

### 版本创建流（文件保存触发）
```
watchdog 检测到 on_modified
  → 防抖 500ms
  → 过滤：扩展名是否为 .docx？是否临时文件（~$*, *.tmp）？
  → 计算文件 MD5，与上一版本哈希对比，相同则跳过
  → 读取文件二进制，zlib 压缩
  → 写入 versions 表（version_number 自增、时间戳、大小、is_auto=1）
  → 检查是否超过 max_versions_per_file，超限则删最旧
  → 发 Qt 信号通知 UI 刷新版本历史
```

### 版本回退流
```
用户点击"回退到此版本"
  → 检查当前文件是否与最新版本不同（被修改未记录）
    → 不同：先自动创建一个备份版本（note="回退前自动备份"）
  → 从数据库取出目标版本的压缩数据
  → 解压，写入临时文件
  → 原子替换原文件（写临时文件 → os.replace，原子操作）
  → 更新文件 mtime 与版本记录一致
  → UI 刷新
```

### 差异比较流
```
用户选两个版本 → 点"比较差异"
  → 取两个版本的压缩数据，解压
  → DocxParser.extract_text() 提取纯文本
  → difflib 计算差异
  → diff_window 左右分栏渲染：新增绿、删除红、修改黄
```

### 托盘与监控生命周期
```
程序启动 → 初始化数据库 → 启动 watchdog Observer → 显示主窗口 → 托盘图标
关闭窗口 → 隐藏到托盘（不退出），监控继续
托盘右键 → 暂停/恢复监控（控制 Observer 的 schedule 状态）
托盘右键 → 退出 → 停止 Observer → 关闭数据库 → 退出
```

## 五、数据库设计

### 表结构
```sql
-- 监控文件夹表
CREATE TABLE monitored_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文件表
CREATE TABLE files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    last_modified TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES monitored_folders(id),
    UNIQUE(folder_id, relative_path)
);

-- 版本表
CREATE TABLE versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    file_size INTEGER NOT NULL,
    modified_by TEXT,
    note TEXT,
    is_auto INTEGER DEFAULT 1, -- 1:自动版本, 0:手动版本
    data BLOB NOT NULL, -- zlib 压缩的完整 docx 二进制
    FOREIGN KEY (file_id) REFERENCES files(id),
    UNIQUE(file_id, version_number)
);

-- 配置表
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### 默认配置
```sql
INSERT INTO config (key, value) VALUES
('max_versions_per_file', '50'),
('retention_days', '30'),
('auto_cleanup_enabled', '1'),
('compression_level', '6');
```

### 数据库位置
- Linux: `~/.local/share/DocHistory/dochistory.db`
- Windows: `%APPDATA%/DocHistory/dochistory.db`
- 通过 `os.name` / `sys.platform` 判断，目录不存在则自动创建

## 六、错误处理与边界情况

### 文件系统边界
- 监控的文件被外部删除 → 数据库保留历史版本，文件列表标记"已删除"，仍可回退/导出
- 文件被占用无法读取（Word 打开中）→ 重试 3 次（间隔 200ms），仍失败则跳过本次版本记录，记日志，下次保存再试
- 监控文件夹被删除/重命名 → 标记 `monitored_folders.is_active=0`，UI 显示"不可用"，不崩溃

### 数据完整性
- 版本写入用数据库事务，失败则回滚，不留半截记录
- 回退时的原子替换：先写 `.dochistory_tmp` 临时文件，成功后 `os.replace` 覆盖原文件
- 数据库超过 100MB 时启动提示用户备份（MVP 仅提示）

### COM 接口降级（doc/wps 在 Linux）
- `Win32DocumentParser` 导入 `win32com` 失败时，类仍可实例化，调用方法抛 `NotImplementedError("doc/wps 支持需要 Windows + Office/WPS")`
- 文件监控遇到 `.doc`/`.wps` 时：记录版本快照（二进制复制可行），但差异比较显示"该格式不支持文本解析"

### 并发
- watchdog 事件在独立线程，UI 在主线程。版本创建后通过 Qt 信号（跨线程安全）通知 UI
- 数据库访问加 `threading.Lock`，避免并发写冲突

### 资源释放
- 退出时：先 `observer.stop()` + `observer.join(timeout=5)`，再关闭数据库
- 托盘图标显式 `tray.hide()`，避免 Linux 残留图标

## 七、界面设计

### 主窗口（方案 B - GitHub Desktop 风格）
```
┌─────────────────────────────────────────────────────────────┐
│ [文件夹下拉 ▼]  |  [搜索文件...]                           │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│  文件 (12)           │  报告.docx                           │
│  ┌────────────────┐  │  5 个版本 · /文档/工作/              │
│  │ 报告.docx  ●  │  │                                      │
│  │ 5版本 · 刚刚  │  │  ● v5  刚刚                          │
│  └────────────────┘  │    自动保存 · 24KB                   │
│  ┌────────────────┐  │                                      │
│  │ 计划.docx      │  │  ○ v4  2小时前                       │
│  │ 3版本 · 2h前   │  │    完成初稿 · 22KB                   │
│  └────────────────┘  │                                      │
│  ┌────────────────┐  │  ○ v3  昨天                          │
│  │ 总结.docx      │  │    自动保存 · 20KB                   │
│  │ 8版本 · 昨天   │  │                                      │
│  └────────────────┘  │  [回退到此版本] [比较差异] [导出]    │
│                      │  [添加备注]                          │
└──────────────────────┴──────────────────────────────────────┘
```

### 差异比较窗口
```
┌─────────────────────────────────────────────────────────────┐
│ 版本差异: 报告.docx (v4 → v5)                          [×] │
├─────────────────────────────┬───────────────────────────────┤
│  v4 (2024-05-20 14:00)      │  v5 (2024-05-20 16:00)        │
│                             │                               │
│  1. 项目背景                │  1. 项目背景                  │
│  2. 目标                    │  2. 目标                      │
│  3. 实施方案                │  3. 实施方案                  │
│                             │  + 增加了新的步骤3.1 (绿)     │
│                             │  ~ 修改了步骤3.2的内容 (黄)   │
│  4. 预算                    │  4. 预算                      │
│                             │  - 删除了原来的预算项 (红)    │
│                             │  + 添加了新的预算项 (绿)      │
│  5. 时间安排                │  5. 时间安排                  │
└─────────────────────────────┴───────────────────────────────┘
```

## 八、测试策略

### 单元测试（pytest，不依赖 GUI）
- `test_database.py` — 建表、增删改查、事务回滚、配置读写
- `test_file_utils.py` — MD5 计算、zlib 压缩/解压、临时文件过滤、路径处理
- `test_document_parser.py` — DocxParser 文本提取（动态生成测试 docx）、Win32DocumentParser 在 Linux 抛 NotImplementedError
- `test_version_manager.py` — 版本创建、哈希去重、回退流程、自动清理、手动备注版本
- `test_diff_utils.py` — difflib 封装：新增/删除/修改行识别与分类

### 集成测试
- `test_file_monitor.py` — 真实创建/修改 docx 文件，验证防抖、过滤、版本记录触发。用 `tmp_path` fixture 隔离
- `test_rollback_flow.py` — 完整流程：创建多版本 → 回退到旧版 → 验证文件内容一致 → 验证自动备份生成

### GUI 测试
- MVP 不做自动化 GUI 测试（PyQt6 测试复杂度高，收益低）
- 手动测试清单：启动、添加监控文件夹、编辑 docx 触发版本、查看历史、回退、diff、托盘行为

### 测试数据
- `tests/fixtures/` 下用 `python-docx` 在测试 setup 中动态生成 docx，避免提交二进制文件

### 测试命令
```bash
pytest tests/ -v
```

## 九、开发计划

### 第1阶段：基础框架
1. 创建项目结构、虚拟环境、安装依赖
2. 实现 SQLite 数据库初始化（database.py）
3. 实现文件监控模块（file_monitor.py + watchdog）
4. 测试文件监控功能

### 第2阶段：核心版本管理
1. 实现文档解析模块（document_parser.py，先做 DocxParser）
2. 实现版本创建/查询功能（version_manager.py）
3. 测试自动版本记录

### 第3阶段：GUI 界面
1. 创建 PyQt6 主窗口（方案 B 布局）
2. 实现监控文件夹管理
3. 实现文件列表和版本历史显示
4. 实现系统托盘
5. 连接 GUI 和核心逻辑

### 第4阶段：版本回退和差异比较
1. 实现版本回退功能
2. 实现文本差异比较（diff_utils.py）
3. 实现差异比较窗口
4. 测试完整流程

### 第5阶段：完善
1. 实现自动清理功能
2. 添加配置管理（settings_window.py）
3. 完善测试覆盖
4. PyInstaller 打包配置（Windows 阶段）

## 十、关键技术决策记录

| 决策点 | 选择 | 理由 |
|-------|------|------|
| 版本存储策略 | 完整快照 | 实现简单、回退直接、无损坏链风险。zlib 压缩后 docx 膨胀仅 10-20% |
| UI 布局 | 方案 B（GitHub Desktop 风格） | 最接近规格书要求，信息层次清晰 |
| 系统托盘 | 完整托盘 | 符合"实时跟踪"语义，后台监控常驻 |
| 差异展示 | 文本行级 diff | 实现简单，difflib 内置，对段落级差异足够直观 |
| doc/wps 处理 | Linux 留空壳，Windows 补全 | 跨平台开发约束，接口预留 |
| GUI 测试 | 手动测试 | PyQt6 自动化测试复杂度高，MVP 阶段收益低 |
