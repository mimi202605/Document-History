# 关键缺陷审查 Spec

## Why
合并分支 trae/solo-agent-HZzj7S 后，需对变更代码进行高影响缺陷审查，确保不会导致数据丢失、应用崩溃或严重功能退化。

## What Changes
审查范围覆盖以下 6 个合并变更文件：
- `build.bat`：构建脚本国际化
- `dochistory/core/database.py`：新增 `get_folder` 方法
- `dochistory/core/file_monitor.py`：删除防抖、原子保存处理
- `dochistory/core/version_manager.py`：相对路径追踪、`_get_folder_path` 辅助方法
- `dochistory/main.py`：初始扫描、normpath 路径匹配、原子保存处理、删除安全检查
- `dochistory/utils/file_utils.py`：扩展临时文件匹配模式

## Impact
- Affected specs: 文件监控、版本管理、删除处理、临时文件过滤
- Affected code: file_monitor.py, version_manager.py, main.py, file_utils.py, database.py

## 审查结论

### 已深度分析的执行路径

1. **`is_temp_file` 模式扩展**（`^~\$` → `^~`）：以 `~` 开头的用户文档文件名在 Windows 上极为罕见，误匹配风险可忽略。`.bak` 和 `^\.~` 扩展合理。

2. **`os.path.relpath` 替代 `os.path.basename`**：正确支持子目录追踪。数据库 UNIQUE(folder_id, relative_path) 约束确保 basename 回退不会匹配错误文件记录。

3. **删除防抖机制**：`_debounce_delete`（1秒窗口）+ `_emit_delete` 中的 `os.path.exists` 检查，正确防止 Word 原子保存导致的误删。竞态条件分析：Timer 操作通过锁同步，`os.path.exists` 提供最终安全网。

4. **初始扫描**：`create_version` 中的哈希检查防止重复版本创建。监控与扫描并发时，最多产生一个额外版本，不会导致数据损坏。

5. **`_find_folder_id_for_path` normpath 改进**：正确防止前缀匹配错误（如 `C:\Doc` 匹配 `C:\Documents`）。

6. **`_on_file_moved` 原子保存处理**：多层防御设计——file_monitor 层过滤标准临时文件，main.py 层通过数据库查找检测非标准临时文件，确保原子保存事件被正确处理为保存而非重命名。

7. **basename 回退安全性**：在 `_on_file_deleted`、`handle_move`、`handle_move_out` 中的 basename 回退，由于 UNIQUE 约束，旧数据库记录中同一文件夹不可能存在同名文件，因此回退不会匹配错误记录。

8. **防抖 Timer 竞态**：`_debounce_delete` 中 timer.start() 在锁外调用是安全的（引用已在锁内存储）。`_emit_delete` 中的 `os.path.exists` 检查消除了 TOCTOU 风险的实际影响。

### 结论
未发现关键缺陷。
