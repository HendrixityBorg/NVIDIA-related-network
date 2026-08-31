# NVIDIA 冻结案例

`frozen_2026-08-25/` 是原 NVIDIA 项目的完整物理目录，研究截点为 2026-08-25。迁移时未改写其中的代码、结果、研究账本或文档；它既是可阅读案例，也是通用框架的回归基准。

核验命令：

```bash
listed-company-network verify-case --manifest case_studies/nvidia/case_manifest.json
```

manifest 固定原提交、关键文件哈希和快照计数。当前快照包含 329 个实体、5,753 个来源、9,458 项证据和 2,016 条关系，其中 supplier 16、customer 180、partner 1,792、investor_or_investee 7、peer 21。

反向复核并非新框架才增加：原案例已对 316 家规范化上市合作伙伴逐家执行监管/IR 复核，形成 48 条商业方向结论（customer 40、supplier 8），22 条 confirmed、26 条 inferred，pending 为 0。详细账本仍位于冻结目录的 `runs/2026-08-25-run-003/agents/partner_regulatory_*`。

冻结案例不是新框架的隐式输入。研究其他公司时，须新建 profile 和 run；查询服务默认指向本案例只为提供开箱可运行的 demo，也可通过 `LCN_DATA_PATH` 切换。
