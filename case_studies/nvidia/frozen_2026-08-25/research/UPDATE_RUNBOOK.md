# 数据更新与复现手册

1. 选择新的研究截点并创建新的运行目录；不得原地修改旧的冻结运行或快照。
2. 在运行 manifest 中记录研究对象法律实体、证券标识、时区、证据起始日期、纳入的来源族和明确排除项。
3. 检查 robots 与公开可访问性。不得使用登录、付费墙、验证码、备用 IP、代理或规避限流的方法；失败应记录为终态访问结果。
4. 重新建立完整产品与解决方案来源边界。每个种子页面、边界内 URL 和页面章节必须在冻结分类树前进入终态。
5. 获取正文前，先枚举全部 Newsroom 与 Blog 归档条目。只有直接正文不可用时才使用公开 RSS 或公开归档回放；只保留结构化事实和哈希，不保留第三方完整页面。
6. 记录运行时 NPN 总量和每页数量，再以串行方式采集。如果总量发生变化，应停止当次分页，记录两个观察值，从第一页按较新的总量重新开始，并且只冻结一个内部一致且完整的总体。不得静默混合来自不同总量的页面。任何集团合并之前必须保留原始地区记录。
7. 仅获取最新 10-K、最新且未修订的 13F 和范围内明确指定的演示材料。核对 13F 报告期、accession、修订状态、单位和每一条证券记录。
8. 使用官方上市或投资者关系证据及精确别名解析法律实体。精确别名未命中不得直接宣告完成；每个候选必须形成符合 `ResearchedEntityResolution` 的研究终态。非上市、已退市、含义不清和被拒绝的候选项保留在决策账本中，不进入活跃上市公司图谱。多个上市主体均合理时，使用同日同币种市值证据选唯一最大者，否则保持歧义。
9. 根据每条证券的实际交易所重新生成 `listing_region`、`listing_region_code` 和实体级 `listing_regions`。不得以公司注册地代替上市地区；遇到未映射交易所时构建必须失败并由人工补充映射。
10. 先建立仅追加的观察，再形成终态关系决策。去重仅使用实体对、方向、关系类型和单一产品范围。
11. 对八个产品大类重新执行可比公司复核，并要求对手方提供自研产品证据；某一大类接受数量为零属于有效决策。
12. 对去重后的全部上市 Partner 做对手方监管材料反向复查。NVIDIA 自身仍只取最新 10-K
    与 13F；对手方可以使用其公开 10-Q、8-K、20-F、6-K、40-F、招股书、年报/中报或
    等价材料。SEC、APAC、EMEA 三路均须输出 terminal frontier、candidates、evidence、
    decision ledger 和 validation，再由统一集成器按五元键合并。公司新闻/媒体最多 inferred；
    每条商业关系必须标注 direct/indirect/both/unclear。访问失败与无命中不得静默删除。
13. 重新计算时效因子和各评分分项。在冲突惩罚之后应用推断/未知状态及供应商/客户上限。
14. 运行遇错即停的最终构建器：

   ```bash
   .venv/bin/python scripts/build_snapshot_v2.py \
     --run-root runs/YYYY-MM-DD-run-NNN \
     --output data/snapshot_YYYY-MM-DD.json \
     --entity-registry-overlay runs/YYYY-MM-DD-run-NNN/agents/non_npn_listing_audit/researched_entity_registry_overlay.jsonl \
     --entity-registry-overlay runs/YYYY-MM-DD-run-NNN/agents/npn_listed_parent_resolution/listed_entity_registry_overlay.jsonl \
     --entity-registry-overlay runs/YYYY-MM-DD-run-NNN/agents/partner_regulatory_entity_normalization/entity_registry_overlay.jsonl \
     --entity-registry-overlay runs/YYYY-MM-DD-run-NNN/agents/partner_regulatory_entity_normalization/sec_cik_entity_registry_overlay.jsonl \
     --entity-merge-map runs/YYYY-MM-DD-run-NNN/agents/partner_regulatory_entity_normalization/entity_merge_map.jsonl
   ```

   发布版本不得使用 `--skip-gates`。
15. 运行 `.venv/bin/python -m compileall -q src scripts tests runs/YYYY-MM-DD-run-NNN`、`.venv/bin/python scripts/validate_snapshot.py --snapshot data/snapshot_YYYY-MM-DD.json`、`.venv/bin/python scripts/audit_delivery.py` 和 `.venv/bin/pytest`。如校验临时构建，应显式传入临时路径，不得依赖仓库中的默认快照。人工冒烟测试应覆盖公司、关系、图谱和证据查询，以及方向、直接性、类型、评分、时间、产品筛选、分页和错误响应。
16. 更新 README 中的统计数字、盲区、来源访问说明、哈希和人工抽样签字。提交 fixture 与快照，使 reviewer 无需重新抓取受限或易变来源即可复核。公开 push 前完成 `DELIVERY_CHECKLIST_ZH.md`，并从干净 clone 复现；本地卫生检查通过不等于公开远端已经验证。

如果任何强制公开来源仍不可用，应保持对应完成门槛为 false，并说明阻塞原因。来源失败代表研究盲区，不构成绕过访问控制或将运行标记为完成的许可。
