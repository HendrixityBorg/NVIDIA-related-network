# 运行手册

## 1. 配置

以 `profiles/nvidia.yaml` 为字段示例创建新的 profile。必须先人工确认目标法律实体、主要证券、上市地区、司法辖区、官方域名、截点、证据窗口和投资关系范围。

## 2. 初始化

```bash
listed-company-network init-run --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
```

初始化会写入确定性的搜索计划、来源种子、目录和 Agent task JSON。禁止复用旧公司的实体或来源账本作为新研究结论。

## 3. Agent 执行顺序

来源发现先运行；监管/IR、官方文章、产品树、生态目录和第三方新闻可并行；随后实体归一；再生成并完成全部上市对手方反向复核；最后裁决关系、研究 peer 和执行 QA。每个 Agent 必须以完整账本和 stage report 交接，聊天摘要不算交付。

## 4. 生成反向任务

当 `entities.jsonl` 和 `relationships.jsonl` 初稿完成后运行：

```bash
listed-company-network review-tasks --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
```

逐项处理 `review/counterparty_tasks.jsonl`，把终态写入 `counterparty_decisions.jsonl`。关系裁决若新增上市实体，必须重新生成/合并任务并补齐新增对象，之后才可验收。

## 5. 验收与构建

```bash
listed-company-network validate-run --profile profiles/target.yaml --run runs/target-YYYY-MM-DD
listed-company-network build-snapshot --profile profiles/target.yaml --run runs/target-YYYY-MM-DD --output data/target-snapshot.json
```

先修复 validation report 中所有 error。不得通过删掉失败记录、放宽 profile 或伪造 complete 状态来绕过门槛；真实访问受阻应保留限制，并由研究负责人决定是否因此不能交付。

## 6. 查询交付

设置 `LCN_DATA_PATH` 后运行 API 或 CLI。reviewer 不需要再次运行研究 Agent或抓取网页；已提交的快照、证据定位、摘录/视觉说明、来源元数据、frontier、裁决和验证报告足以理解判断。
