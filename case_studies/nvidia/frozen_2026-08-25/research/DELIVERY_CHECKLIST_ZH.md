# 公开交付检查清单

本清单用于将本地、冻结的 NVIDIA 上市公司关系研究服务整理为公开 GitHub 提交。
研究截点仍为 `2026-08-25`；收尾工作不会把 2026-08-26 之后的信息混入快照。

## 已由确定性检查完成

- [x] 20 个强制数据族均 `pass`、`pending=0`，coverage frontier 为 release-ready；
- [x] 正式快照通过 Pydantic 模型、关系五元组、证据引用、上市标识与评分校验；
- [x] 316 个 canonical Partner 全部具有监管复查终态；
- [x] 16 条 Supplier 关系逐条输出公司、证券、供应类别、产品、直接性、分数和主证据；
- [x] 本轮新增 confirmed supplier/customer 全部具有明确监管主证据；
- [x] SEC 新闻附件、业绩稿、电话会稿和保守处理的 6-K 公司公告不会单独生成 confirmed；
- [x] 同一文件只选一个最强 primary context，其余重复上下文为 corroborating；
- [x] 同一 publisher 的重复文件和上下文不增加 independence 分；
- [x] inferred supplier/customer 均低于 60 分；
- [x] API/CLI 支持类型、方向、直接性、产品、分数、时间、unknown、分页与明确错误响应；
- [x] 项目内无 `.env`、私钥文件、高特异性密钥命中或超过 20 MB 的单文件；
- [x] README、LICENSE、`.gitignore`、`.env.example`、依赖及复现命令存在。

确定性结果见：

- `runs/2026-08-25-run-003/delivery_review/delivery_audit_report.json`
- `runs/2026-08-25-run-003/delivery_review/supplier_audit.jsonl`
- `runs/2026-08-25-run-003/delivery_review/new_confirmed_commercial_audit.jsonl`

## 提交者人工复核

- [x] 对 16 条 Supplier 逐条打开主证据并签字确认，尤其区分芯片/制造供应与云服务供应；
- [x] 对 22 条本轮新增 confirmed 商业关系逐条签字确认；
- [x] 在不复制 `.venv`、缓存和字节码的临时干净目录重新安装依赖，并通过快照校验、交付审计、50 项测试及 CLI 冒烟；
- [x] 将人工复核日期、提交者标识和例外说明写入签字清单；
- [x] 最终确认“不构成投资建议”在 README、API meta 和快照中均可见。

签字范围以关系 ID 集合的数量和 SHA-256 绑定在
`research/HUMAN_REVIEW_SIGNOFF.json`。交付审计只有在集合未变化时才写出
`human_verified=true`。公开 GitHub remote、push 和托管平台扫描不属于本次本地完成范围。

## 最终命令

```bash
make build
make validate
make delivery-audit
make compile
make test
make smoke
git diff --check
```

本研究使用合法公开资料并保留访问边界，不构成投资建议。
