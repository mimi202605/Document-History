# 关键缺陷审查与修复 Spec

## Why
DocHistory 是一个负责追踪 .doc/.docx/.wps 文档编辑历史、支持回滚的离线文档版本管理工具。其核心价值在于"数据不丢失"。一旦数据库写入、版本捕获、文件监听或回滚链路中存在静默数据丢失、并发竞态、崩溃路径或资源泄漏，将直接导致用户历史版本不可恢复——这是该类工具最严重的事故。本次审查以"高级代码正确性审查引擎"视角，对当前代码库进行一次定向的、以高影响缺陷为唯一目标的审查与修复。

## What Changes
- 对 `dochistory/core/`（database、version_manager、file_monitor、document_parser）执行深度调用链审查，定位会导致数据丢失/崩溃/并发缺陷/资源泄漏的关键 Bug。
- 对 `dochistory/utils/`（diff_utils、file_utils）与 `dochistory/ui/` 中影响业务正确性的关键路径进行审查。
- 对每个**确认且可构造具体触发场景**的 Bug：实施最小化定向修复，并补充覆盖触发路径的测试用例。
- 严格遵守边界：不重构、不清理无关代码、不扩展功能；修复不得引入新 Bug 或破坏现有逻辑。
- 若审查后未发现符合"高影响 + 可复现触发场景"门槛的缺陷，则仅输出标准结论"未发现关键缺陷。"，不强行制造问题。

## Impact
- Affected specs: 文档版本捕获、版本回滚、文件监听、数据库持久化、并发安全。
- Affected code:
  - `dochistory/core/database.py`（SQLite 线程安全、事务、外键、清理逻辑）
  - `dochistory/core/version_manager.py`（版本号生成、原子写入、回滚）
  - `dochistory/core/file_monitor.py`（文件系统事件去重、并发回调、防抖）
  - `dochistory/core/document_parser.py`（文档读取、异常处理）
  - `dochistory/utils/file_utils.py`、`dochistory/utils/diff_utils.py`
  - `tests/`（新增针对每个修复的回归测试）

## ADDED Requirements

### Requirement: 关键缺陷审查
系统 SHALL 对当前代码库执行一次以"数据丢失/崩溃/并发缺陷/资源泄漏"为唯一焦点的高影响缺陷审查。

#### Scenario: 仅报告可复现的高影响缺陷
- **WHEN** 审查引擎发现一个疑似 Bug
- **AND** 能够构造出包含前置条件、触发步骤、具体错误表现的可复现触发场景
- **THEN** 将其确认为关键缺陷并进入修复流程
- **AND** 输出包含根因、触发场景、影响范围的诊断说明

#### Scenario: 不可复现的疑似问题视为误报
- **WHEN** 审查引擎发现一个疑似 Bug 但无法构造出真实环境中可复现的具体触发条件
- **THEN** 将其视为误报，不报告、不修复

### Requirement: 定向修复
系统 SHALL 对每个确认的关键缺陷实施最小化、高置信度的修复。

#### Scenario: 修复仅针对当前缺陷
- **WHEN** 实施修复
- **THEN** 修改范围严格限定于该缺陷的触发路径
- **AND** 不混入大范围重构、无关清理或功能扩展
- **AND** 不破坏现有逻辑或引入新 Bug

### Requirement: 回归测试覆盖
系统 SHALL 为每个修复补充测试用例，精确覆盖缺陷触发路径与修复后预期行为。

#### Scenario: 修复附带回归测试
- **WHEN** 一个缺陷被修复
- **THEN** 新增或更新测试用例，能够在修复前失败、修复后通过
- **AND** 全量测试套件运行通过，无回归

### Requirement: 无缺陷结论
系统 SHALL 在未发现符合门槛的关键缺陷时，输出标准结论而非强行制造问题。

#### Scenario: 审查无关键缺陷
- **WHEN** 审查完成且未发现任何符合"高影响 + 可复现触发场景"门槛的缺陷
- **THEN** 仅输出标准结论"未发现关键缺陷。"
- **AND** 不附加额外解释或低优先级问题清单

## MODIFIED Requirements

### Requirement: 代码审查边界
审查范围限定为高影响缺陷（数据完整性、并发与同步、崩溃风险、资源管理失控）。代码风格、命名规范、轻微性能优化等低优先级问题 SHALL 被主动忽略，不进入修复流程。
