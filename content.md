## commit: fix: 在双写时实时写入 owner_id 至数据库

~~~~~act
git_add .
~~~~~
~~~~~act
git_commit
~~~~~
~~~~~
fix: 在双写时实时写入 owner_id 至数据库

当前的 `SQLiteHistoryWriter` 在执行“双写”操作时，虽然会将节点元数据写入 SQLite，但其 `INSERT` 语句遗漏了 `owner_id` 字段。

这导致新创建的本地节点的 `owner_id` 在数据库中为空，直到下一次 `sync` 或 `align` 触发数据补水 (`Hydrator`) 时才被填充。这种延迟破坏了数据的一致性。

此提交通过在写入路径上直接注入所有者信息，确保了 SQLite 缓存始终是 Git 底层状态的准确反映。
~~~~~
