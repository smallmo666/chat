# 架构前缀与列映射配置

- DEFAULT_QUERY_SCHEMA：通过环境变量配置默认查询前缀，例如 `reverse_logistics`。当 DSL 中的表未显式带前缀时，会自动补充。
- 列映射文件：`src/config/column_mapping.json`，用于将 DSL 中的列名映射到实际数据库列，例如：

```json
{
  "orders.itemcode": "orders.product_code",
  "orders.txndate": "orders.txn_date"
}
```

- 预检与澄清：在编译前会校验表与列是否存在，缺失时返回澄清消息并给出相似列名建议。
- 审计日志：`executed_sql` 字段为 Text 类型，并在保存前进行安全截断以避免长度异常。MySQL 迁移脚本位于 `migrations/mysql/20260108_alter_audit_logs.sql`。
