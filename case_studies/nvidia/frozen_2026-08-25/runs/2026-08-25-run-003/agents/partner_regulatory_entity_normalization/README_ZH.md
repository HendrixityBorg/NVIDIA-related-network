# Partner 监管材料反向复查：实体规范化前置

研究截点：**2026-08-25**。本目录只读取 `data/snapshot_2026-08-25.json`，不修改最终 snapshot 或主构建器。目标是为后续 Partner 监管材料复查提供一个去重后的上市主体全集，同时让所有原实体、证券、NPN 标签、关系、证据和来源仍可追溯。

## 范围与规则

输入范围是当前 snapshot 中 `relation_type=partner` 所连接的全部 `listing_status=listed` 实体，共 329 个原实体 ID。

确定性合并键按以下顺序并集：

1. 精确 CIK；
2. 规范化交易所名称后的精确 `exchange:ticker`；
3. 精确 ISIN；
4. 仅做 Unicode、大小写、标点和空白规范化后的精确法律名称。

不会删除 `technology`、`systems`、`group` 等实词或法律后缀，不使用编辑距离、token 相似度或模糊匹配。任何多重上市、不同股类、ADR/OTC、本币/RMB 柜台或状态字段不一致的证券都会全部保留，并进入 `manual_multilisting_review.jsonl`，不会自动选择一个证券覆盖其他证券。

canonical ID 选择优先级是：含 CIK、含 ISIN、证券信息更完整、截点状态更完整，最后才考虑 ID 稳定性。合并只影响下游建议端点；`entity_merge_map.jsonl` 会保留每个原实体的完整记录以及它参与的全部 Partner 关系 ID。

## 输出

- `canonical_partner_universe.jsonl`：规范化 Partner 上市主体；聚合全部证券、别名、关系、证据、来源记录及 NPN tags。
- `entity_merge_map.jsonl`：329 个原实体逐一映射至 canonical ID，0 pending；完整保留原实体对象。
- `entity_registry_overlay.jsonl`：仅列出实际发生重复合并的 canonical registry overlay。
- `manual_multilisting_review.jsonl`：待人工判断的多重上市/多证券队列，不丢弃任何证券。
- `validation_report.json`：独立验证结果。

已精确修复题目指定的十组重复：CoreWeave、Equinix、T-Mobile、Alibaba、Booz Allen、Elastic、Eaton、TD SYNNEX、Verizon、Quanta。确定性规则还识别出 Deutsche Telekom、SoftBank Group、Tencent 三组重复。

## 复现与测试

无需网络、密钥或真实凭据：

```bash
python3 build.py
python3 validate.py
python3 -m unittest -v test_normalization.py
```

验证门包括：329 个原 Partner 上市实体全部且仅映射一次；canonical partition 闭合；至少十个指定重复组全部修复；所有 merge basis 均为精确标识；关系、证据、来源引用闭合；原证券和 NPN 标签保留；多重上市队列不为空且未静默丢弃证券。

## 下游合并约定与限制

后续 builder 应先用 `entity_merge_map.jsonl` 重写 Partner 关系端点，再按规范关系键去重；相同关系键必须并集 evidence IDs、source IDs、NPN group IDs、partner types、competencies、specializations、partner levels、locations 与 product/service tags。原实体应保留为 alias/provenance，不应从审计交付中删除。

本层不判断哪一个证券是监管材料检索的唯一主证券。20 个主体含两个或以上尚标为 active/未明确 historical 的交易所代码，其中既有合法双重上市和多股类，也有可能的债券/优先证券或状态缺失，均保留给后续人工复查。没有标识命中的 singleton 只表示本 snapshot 内未发现精确重复，不表示已经完成全球法律主体穿透。
