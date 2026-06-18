# Tasks

- [ ] Task 1: 审查 `dochistory/core/database.py` 的关键缺陷
  - [ ] SubTask 1.1: 检查 SQLite 单连接 + 单锁在多线程下的并发安全性（check_same_thread=False + threading.Lock 是否覆盖所有读写路径，是否存在事务跨方法调用导致的隐式串行化问题或锁重入死锁）
  - [ ] SubTask 1.2: 检查 `cleanup_old_versions` 删除逻辑是否会误删最新版本或破坏版本号唯一性约束，验证 `max_versions` 边界（0、负数、超过现有版本数）
  - [ ] SubTask 1.3: 检查 `get_latest_version_number` 在并发写入下是否返回陈旧值导致版本号冲突（UNIQUE(file_id, version_number) 触发 IntegrityError 未捕获）
  - [ ] SubTask 1.4: 检查 `update_file_hash` 签名包含 `new_size` 但 SQL 未使用该参数是否导致数据不一致
  - [ ] SubTask 1.5: 检查 `close()` 后再调用方法是否引发未处理异常，以及连接未在异常路径下正确释放

- [ ] Task 2: 审查 `dochistory/core/version_manager.py` 的关键缺陷
  - [ ] SubTask 2.1: 追踪版本捕获完整调用链：监听事件 → 哈希计算 → 版本号生成 → 数据写入，定位丢失更新或重复写入
  - [ ] SubTask 2.2: 检查回滚流程是否原子（写文件 + 更新数据库状态），中途失败是否导致文件与版本记录不一致
  - [ ] SubTask 2.3: 检查文件读取/写入是否使用临时文件 + 原子替换，避免崩溃导致目标文件损坏
  - [ ] SubTask 2.4: 检查异常处理是否吞掉关键错误导致静默数据丢失

- [ ] Task 3: 审查 `dochistory/core/file_monitor.py` 的关键缺陷
  - [ ] SubTask 3.1: 检查文件系统事件去重/防抖逻辑是否在快速连续保存下丢失版本
  - [ ] SubTask 3.2: 检查监听器回调是否在监听线程中执行阻塞 IO 导致事件丢失或线程阻塞
  - [ ] SubTask 3.3: 检查重命名/移动事件处理是否正确迁移版本历史，避免历史断裂
  - [ ] SubTask 3.4: 检查监听器启动/停止资源管理是否泄漏文件句柄或线程

- [ ] Task 4: 审查 `dochistory/core/document_parser.py` 与 `dochistory/utils/` 的关键缺陷
  - [ ] SubTask 4.1: 检查文档解析异常是否导致整个监听流程崩溃
  - [ ] SubTask 4.2: 检查 `file_utils` 中路径处理、临时文件清理的资源泄漏
  - [ ] SubTask 4.3: 检查 `diff_utils` 中集合越界、空输入导致的崩溃路径

- [ ] Task 5: 汇总确认缺陷并实施定向修复
  - [ ] SubTask 5.1: 为每个确认缺陷构造可复现触发场景（前置条件 + 触发步骤 + 错误表现）
  - [ ] SubTask 5.2: 实施最小化定向修复，仅触及缺陷触发路径
  - [ ] SubTask 5.3: 为每个修复新增/更新测试用例，覆盖触发路径与修复后预期行为

- [ ] Task 6: 运行全量测试验证无回归
  - [ ] SubTask 6.1: 执行 `pytest tests/` 确认所有测试通过
  - [ ] SubTask 6.2: 确认修复未破坏现有测试，新增测试在修复前失败、修复后通过

# Task Dependencies
- [Task 5] 依赖 [Task 1]、[Task 2]、[Task 3]、[Task 4] 的审查结论
- [Task 6] 依赖 [Task 5] 的修复完成
- [Task 1]、[Task 2]、[Task 3]、[Task 4] 可并行执行
