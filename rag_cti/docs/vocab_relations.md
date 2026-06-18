# 词表关系清单 (Controlled Relation Vocabulary)

> **数据驱动生成**自 `facts.jsonl`(M3 `build_facts` over the chunk corpus)。
> 受控谓词的权威定义见 `docs/CONTEXT.md §Fact`;本表只列**实际出现**的
> `(谓词, 主语类型, 宾语类型)` 组合 + 数据源 + Fact 计数 + 一个示例。
> 示例显示可读名 + 括号内的 entity_id(join 键);MITRE 编号 id(`actor_G0016`/`technique_T1059`…)= 已解析到 ATT&CK,带 hash 的(`indicator_…`/`*_orphan_…`)= 无 MITRE 对象、按值/名哈希出的稳定 id。
> 重新生成即可刷新(`scripts/build_vocab_relations.py`)。

合计 14 个关系模式,43776 条 Fact。


## TTP / 归因 (attribution)

| 谓词 | 主语类型 | 宾语类型 | 数据源 | Fact 数 | 示例 |
|---|---|---|---|---|---|
| `attributed-to` | campaign | actor | mitre | 25 | C0011 (`campaign_C0011`) → Transparent Tribe (`actor_G0134`) |
| `targets` | actor | location | otx | 1016 | Ke3chang (`actor_G0004`) → Portugal (`location_orphan_069f2de691fa32f1`) |
| `uses` | family | technique | mitre | 10636 | Trojan.Mebromi (`family_S0001`) → System Firmware (`technique_T1542.001`) |
| `uses` | actor | technique | mitre, otx | 8522 | Axiom (`actor_G0001`) → Steganography (`technique_T1001.002`) |
| `uses` | actor | family | mitre, otx | 2871 | Axiom (`actor_G0001`) → Hikit (`family_S0009`) |
| `uses` | campaign | technique | mitre | 1019 | Frankenstein (`campaign_C0001`) → Data from Local System (`technique_T1005`) |
| `uses` | campaign | family | mitre | 149 | Frankenstein (`campaign_C0001`) → Empire (`family_S0363`) |

## 基础设施 (infrastructure)

| 谓词 | 主语类型 | 宾语类型 | 数据源 | Fact 数 | 示例 |
|---|---|---|---|---|---|
| `belongs-to` | indicator | asn | pdns | 4542 | 150.171.28.10 (`indicator_56c8dd787f36bcfc`) → `asn_9592848a893d44d6` |
| `has-subdomain` | indicator | indicator | pdns | 1055 | 07ob52279142.application-e68-x4o.stream (`indicator_069a98ce7a695b16`) → alert1076.07ob52279142.application-e68-x4o.stream (`indicator_d54198189212da2a`) |
| `located-in` | indicator | location | pdns | 4512 | 150.171.28.10 (`indicator_56c8dd787f36bcfc`) → United States (`location_orphan_db833939c809aa3a`) |
| `resolves-to` | indicator | indicator | pdns, virustotal | 6028 | 0207xygulya8.pro (`indicator_04b8c6be666f6dae`) → 18.172.170.4 (`indicator_966edc78684c567e`) |
| `uses-nameserver` | indicator | indicator | pdns, virustotal | 1265 | 0871.com.cn (`indicator_059a51f8f736c6d5`) → ns1.bodis.com (`indicator_0f9d04082c621f7b`) |

## 防御 (defensive)

| 谓词 | 主语类型 | 宾语类型 | 数据源 | Fact 数 | 示例 |
|---|---|---|---|---|---|
| `detects` | detection-strategy | technique | mitre | 691 | Detect Access to Cloud Instance Metadata API (IaaS) (`detection-strategy_DET0001`) → Cloud Instance Metadata API (`technique_T1552.005`) |
| `mitigates` | mitigation | technique | mitre | 1445 | Application Developer Guidance (`mitigation_M1013`) → Valid Accounts (`technique_T1078`) |
