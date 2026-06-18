# Checklist

- [x] `dochistory/core/database.py` 已完成并发安全、清理逻辑、版本号冲突、参数一致性、连接生命周期审查
- [x] `dochistory/core/version_manager.py` 已完成版本捕获链路、回滚原子性、原子写入、异常吞没审查
- [x] `dochistory/core/file_monitor.py` 已完成事件去重、回调阻塞、重命名迁移、资源泄漏审查
- [x] `dochistory/core/document_parser.py` 与 `dochistory/utils/` 已完成解析异常、资源泄漏、越界崩溃审查
- [x] 每个确认缺陷均附带可复现触发场景（前置条件 + 触发步骤 + 错误表现）
- [x] 每个修复均为最小化定向修改，未混入重构/清理/功能扩展
- [x] 每个修复均新增或更新测试用例，覆盖触发路径与修复后预期行为
- [x] 全量 `pytest tests/` 通过（102 passed），无回归
- [x] 若无符合门槛的缺陷，仅输出"未发现关键缺陷。"标准结论
