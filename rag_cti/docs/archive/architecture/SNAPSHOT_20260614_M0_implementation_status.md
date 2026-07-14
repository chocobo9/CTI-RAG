# SNAPSHOT — M0 入口层重构实施状态（2026-06-14）

> Archive category: architecture milestone status.
>
> **Status: HISTORICAL SNAPSHOT. Do not use this file for current project status,
> current collection state, or current implementation planning.** It is retained as
> dated verification evidence. Current subsystem authorities must be consulted instead.

> 分支 `feat/optimization`(worktree `.claude/worktrees/optimization/`,base `cd481c5` ← `feat/cti-eval-certification`)。
> 本文记录截至 2026-06-14 的实现、验证证据、产出数据、与未完成项。**全部数字均为本轮实跑验证,非文档原值。**
> 状态:**W0–W11 全部完成。W10 v3 重认证 4 项能力门控全 PASS(CTI-ATE Micro-F1 0.67→0.86,见 §10);全部改动 commit 在 `feat/optimization`,未 push。**

> Intermediate v0.1 addendum (2026-06-28): Stage 1 intermediate delivery now
> lives at `data/deliveries/intermediate_v0_1_2026-06-28.zip`. For the current
> data-processing contract and handoff state, see
> `docs/intermediate/contract_draft.md`,
> `docs/intermediate/deferred_questions.md`,
> `docs/intermediate/SNAPSHOT_20260628_schema_dry_run_10_records.md`, and
> `scripts/build_intermediate_v0_1_delivery.py`. This addendum does not change
> the older M0/RAG status below.

---

## 0. 范围与两个拍板决策

本轮做的是 **M0(入口层 / L0:去丢数据)**,外加把 M0 语料灌进一个新 Qdrant collection 做 A/B。**M2 检索层改动(payload 索引、relations[] 存 entity_id、丢模板首行、query 期本体展开、截断 logging)未做**(见 §6)。

- **决策①(MITRE 关系/源类型)**:事实边 `_CTI_REL_TYPES={uses, attributed-to}`,主语限威胁实体 `_CTI_SOURCE_TYPES={intrusion-set, campaign, malware, tool}`。`mitigates`/`detects` 不收(防御侧主语);`subtechnique-of`、technique→tactic 作**本体边**单独产出。`targets` 不在 MITRE bundle。
- **决策②(indicator)**:indicator 是 Knowledge-Layer **Entity**,不是 payload metadata。全量进 raw + 独立 `indicator_index.jsonl`;Qdrant payload 不背全量(单 pulse 可达 2 万 indicator)。`actor_ids` 关联留接口不填(M1)。
- **Rule 0 强制**:indicator `type` 逐字保留源类型;`hostname→domain`、`URI→url` 加 canonical 映射(源 type 仍保留),其余无对应的(BitcoinAddress/CIDR/CVE/FilePath/Mutex/SSLCert/YARA)`canonical_type=null` 保留不丢。

> ⚠️ 以上仅结论摘要。**每个决策的完整记录(原始冲突 / 选项 / 用户原话理由 / 落地)见 §9**。
> 命名注意:本轮「决策 ①②③④」是本次新拍/新定的,与设计文档自带的 `DECISION-1…5`(门控 M1/M3)**是两套编号**,§9 已区分。

---

## 1. 工作流与状态总表

| W | 内容 | 状态 | 验证证据 |
|---|---|---|---|
| W0 | worktree 数据接线 | ✅ | `data/raw` junction→主仓库;WSL venv 跑 worktree 代码 |
| W1 | 版本化 RawStore(append-only/永不覆盖/冲突 fail-loud) | ✅ | `store/raw_store.py` + 10 单测 |
| W2 | indicator 类型化(Rule0 保留源 type) | ✅ | `preprocess/indicators.py` + 单测;真实 OTX 验证 |
| W3 | indicator_index(entity 形态)+ pDNS join 字段 de-cap | ✅ | `preprocess/indicator_index.py`、`build_indicator_index.py`、`passive_dns.py` |
| W4 | MITRE 带宽化(决策①,+malware/tool) | ✅ | 真实 bundle **17,295 docs(+10,636)** |
| W4b | 本体边产出(subtechnique-of / technique→tactic) | ✅ | 真实 bundle **477 + 905 = 1,382 边** |
| W5 | id 碰撞 fail-loud | ✅ | `qdrant_store.assert_unique_chunk_ids` + ingest 串 seen_ids;真实 22,840 chunk 无碰撞 |
| W6 | 增量(RawStore high-water + fetch_to_raw) | ✅ | `ingest/raw_ingest.py` + 单测 |
| W7 | VT/WHOIS/pDNS raw fetcher | ✅ | vt/whois 可跑;pdns 占位 guard;`PDNS_API_KEY` 占位 |
| W8 | per-source 声明式归一(§4) | ✅ | `ingest/normalize.py`;真实 2,056 pulses / 17,295 rels 各 0 error |
| W9 | reconcile rebuild(RawStore 确定性) | ✅ | 迁移真跑 2,056+1;rebuild **两次字节一致** |
| W10 | 建 cti_chunks_v3 + 重认证 | ✅ | v3 建(20,759 pts)+ eval-all 全 DeepSeek 重认证,4 项门控全 PASS(见 §10) |
| W11 | gitignore 放开 pdfs + docs 断链 + ci | ✅ | gitignore 已验;6 设计文档 copy 进 worktree `docs/` + `/CONTEXT.md`→`docs/CONTEXT.md`(11 处/5 文件)修复并 commit |

**CI(`make ci`,worktree)**:ruff ✅ · ruff format ✅ · mypy 0(59 files)✅ · pytest **641 passed / 10 skipped / coverage 89.53%** ✅。

---

## 2. 新增 / 改动的代码

### 新模块(src,mypy strict + 测试覆盖 90–100%)
- `store/raw_store.py` — 版本化 RawStore(`{source}/{source_id}/{fetched_at}.json`,冲突 `RawStoreConflictError`)
- `preprocess/indicators.py` — `IndicatorMention{value,type,canonical_type}` + 源→canonical 映射
- `preprocess/indicator_index.py` — indicator 作 entity 的索引构建
- `preprocess/ontology_edges.py` — STIX → 公理本体边
- `ingest/raw_ingest.py` — `fetch_to_raw` + `read_domains_from_index`
- `ingest/normalize.py` — `NormalizedRecord` + 结构源零推断产 entity/relation mention

### 改动
- `connectors/mitre_relationship.py` — `_CTI_SOURCE_TYPES` += malware/tool
- `connectors/passive_dns.py` — join 字段(ips/asns/subdomains)去 cap
- `connectors/whoxy.py` — 加 `whois_raw`/`history_raw`(存 verbatim)
- `store/qdrant_store.py` — `assert_unique_chunk_ids` + `ChunkIdCollisionError`
- `bootstrap.py` / `__init__.py` — **稀疏词表硬编码修复**(见 §5)

### 新 / 改脚本
- 新:`build_indicator_index.py`、`build_ontology_edges.py`、`migrate_raw_store.py`、`refetch_vt_raw.py`、`refetch_whois_raw.py`、`refetch_pdns_raw.py`(占位)
- 改:`ingest.py`(`--sparse-vocab`、id 碰撞守卫)、`rebuild_otx_jsonl.py`(读 RawStore,确定性 retrieved_at)

---

## 3. 产出的数据工件

### 在 Qdrant:`cti_chunks_v3`(20,759 pts;`cti_chunks_v2` 10,123 全程冻结)
| source(payload) | v3 | v2 | 说明 |
|---|---:|---:|---|
| mitre | 18,061 | 7,425 | techniques 766 + relationships(v3 17,295 / v2 6,659) |
| otx | 2,072 | 2,072 | chunk 数同;metadata.indicators 收窄(全量搬进 index) |
| pdf | 626 | 626 | 未变 |

**v3 关系全景(17,295 条;谓语只有 uses 17,270 + attributed-to 25,无新谓语)**:

| 子 -谓-> 宾 | 数量 | 新? |
|---|---:|---|
| malware -uses-> technique | 9,836 | **新** |
| actor -uses-> technique | 4,362 | |
| campaign -uses-> technique | 1,019 | |
| tool -uses-> technique | 800 | **新** |
| actor -uses-> malware | 647 | |
| actor -uses-> tool | 457 | |
| campaign -uses-> malware | 84 | |
| campaign -uses-> tool | 65 | |
| campaign -attributed-to-> actor | 25 | |

→ **Qdrant 新增 = 10,636 条 malware/tool→uses→technique「软件能力边」。**

### 库外旁路工件(M1/M2 消费,不嵌入)
- `data/processed/indicator_index.jsonl` — **229,883 个类型化 indicator entity**:domain 64,589 / hash-sha256 59,985 / url 54,295 / hash-md5 27,110 / hash-sha1 20,750 / email 2,022 / ipv4 147 / ipv6 1 / canonical=null 984。`hostname→domain`、`URI→url` 映射使 null 从 33,209 降到 984。
- `data/processed/ontology_edges.jsonl` — **1,382 条**(477 subtechnique-of + 905 technique→tactic)
- 版本化 RawStore(`data/raw/{otx,mitre}/{id}/{fetched_at}.json`)— 迁移 2,056 OTX + 1 MITRE bundle
- `data/sparse_vocab_cti_chunks_v3.json` — v3 专属 BM25 词表(**43,857 token**,fit on v3 语料)
- v3 staging 语料:`data/processed/v3_staging/*.jsonl`(otx 2,072 + mitre_relationships 17,295 + mitre 766 + pdfs 626)

---

## 4. 截断 / chunk size 现状(已澄清:**库里数据是全的**)

- **chunk 策略**:SEMANTIC(叙事,600 token 软目标 + 80 overlap,长句不切)/ STRUCTURED(关系边、field 源,一记录一 chunk 不切)。
- **写入 Qdrant 无截断**:实测 v3 最长 chunk = **3,463 字符**(otx);0 chunk 超 8,000 字符。token ≤ 字符,故 ≤3,463 token « 8,192(BGE-M3 嵌入上限)。`_chunk_to_payload` 存全文,8,000 char 是读时 cap 且无 chunk 触及。dense+sparse 向量在**全文**上算。
- **唯一截断 = reranker 查询期评分**:`reranker.py` `CrossEncoder(max_length=512)`(认证锁定 512)。它截的是**算分时的 (query,chunk) 输入**,**不改库里存的内容、也不改向量**;长 chunk 仍完整存储/返回,只是重排打分只看前 512 token。
- audit(`docs/archive/eval/SNAPSHOT_cti_chunks_v2_chunk_truncation_audit.md`,v2)记 OTX 42% chunk 超 512 token → 这些 chunk 重排打分被截尾,但**数据完整**。

---

## 5. 稀疏词表硬编码修复

原硬编码 `data/sparse_vocab.json`(三处:`ingest.py`、`bootstrap.py`、`__init__.py`)。已修:
- `ingest.py` 加 `--sparse-vocab PATH`(不存在则 fit+存);
- `bootstrap.vocab_path_for(collection)` 按 collection 自动配对 `sparse_vocab_{collection}.json`,存在用、否则回退默认 → **eval/cert 脚本零改动**即取对词表;
- `build_retrieval_stack(vocab_path=None)` 默认走配对;`__init__` 默认 pipeline 同步;
- v2 不受影响(无 specific 文件 → 仍用 `sparse_vocab.json`)。

---

## 6. 未完成 / 待决项

| 项 | 状态 | 说明 |
|---|---|---|
| **eval-all 重认证 v3** | ✅ | 2026-06-15 全 DeepSeek(`--gen-provider deepseek` 绕开 Groq TPD)跑完,4 项 PASS,见 §10 |
| **worktree/main 数据错位** | ✅ | 词表×2 + `data/eval/ctibench/` + `.env` copy 进 worktree(均 gitignored);零 LLM smoke + eval-all 实跑双验 |
| **M2 检索层** | ⚠️ 代码完成,未接 live | M2.1–M2.5 代码 + 测试已完成(`33b33a6`/`c991dcc`/`afa7e7a`/`2daae9e`/`7feec6b`)+ 投影正确性修复(`24a24d0`)。**但 `project_chunk` 未接进 corpus-build,`cti_chunks_v3` payload 不含这些字段**——M2 过滤/索引只在临时测试 collection 验过。接线+重灌 v4 = M2.6(未做)。截断 logging 仍未做(下行) |
| **截断 logging(§6 Rule0)** | ❌ | reranker 512 仍静默截断,文档要求 log/flag,未做 |
| **docs 断链修复** | ✅ | 6 个设计文档 copy 进 worktree `docs/`;`/CONTEXT.md`→`docs/CONTEXT.md`(11 处/5 文件)已修;本次 commit 一并提交 |
| **VT/WHOIS raw 真抓** | ❌ | 脚本可跑但未发真 API(配额);pdns 无 provider 占位 |
| **未 push** | ⚠️ | M0 主体/原子写/PDF/docs/gitignore/cert 证据全 commit 在 `feat/optimization`,**未 push** |

**重要定性**:`cti_chunks_v3` = **M0 语料灌进新 collection**,**不是完整的 M2 检索增量**。拿它认证测的是「M0 语料增益 + 旧检索机制」。

---

## 7. 复现 / 运行命令

```bash
# 跑测试/CI(WSL venv + worktree PYTHONPATH)
cd <worktree>/rag_cti
PYTHONPATH=<worktree>/rag_cti/src <venv>/python -m pytest -q
<venv>/python -m ruff check src/ tests/ scripts/ && <venv>/python -m mypy src/

# 数据流水(主仓库 cwd,有真实 data/)
python scripts/migrate_raw_store.py                    # flat raw → 版本化 RawStore
python scripts/build_indicator_index.py                # → indicator_index.jsonl
python scripts/build_ontology_edges.py                 # → ontology_edges.jsonl
python scripts/rebuild_otx_jsonl.py --out <staging>/otx.jsonl          # 确定性
python scripts/seed_mitre_relationships.py --out <staging>/mitre_relationships.jsonl  # 带宽化 17,295

# 灌 v3(GPU)
python scripts/ingest.py --processed-dir <staging> \
  --sources mitre mitre_relationships otx pdfs \
  --collection cti_chunks_v3 --sparse-vocab data/sparse_vocab_cti_chunks_v3.json \
  --device cuda --batch-size 32

# 重认证(未跑,需 go;需先解决词表路径错位)
make eval-all COLLECTION=cti_chunks_v3
```

---

## 8. 环境备注
- 代码全在 worktree;`data/raw` 经 junction 指向主仓库(gitignore);跑脚本需 `PYTHONPATH=<worktree>/rag_cti/src`。
- Qdrant 在 Docker(`rag_cti-qdrant-1`,localhost:6333),需 Docker Desktop 运行。
- 嵌入用 GPU(RTX 3060 Ti 8GB,torch cu118,`--device cuda`,batch 32 防 OOM)。v3 嵌入实测 ~39 分钟(PDF 长 chunk 主导)。
- `.env` 有 OTX/VT/WHOXY/DeepSeek/Groq key;`make ci` = lint+fmt+type+test 全阻断。

---

## 9. 决策记录(完整,可追溯)

> **命名澄清**:本节「本轮决策 ①②③④」是本次实施中新拍/新定的。与设计文档自带的 `DECISION-1…DECISION-5`(D1 fuzzy 不自动 merge、D2 orphan、D3/D4 aggregate confidence、D5 conflict represent;门控 M1/M3)**不是同一套**。D1–D5 本轮**未触及**(M1/M3 未做)。

### 本轮决策①——MITRE 关系/源类型〔用户拍板〕
- **原始冲突**:ingestion §2 表说"widen `_CTI_REL_TYPES` 到 bundle 存在的所有类型";knowledge §3/§4 说受控谓语只 `uses/attributed-to/targets`、且 `subtechnique-of` 是**本体边**(非事实边)。两者矛盾。
- **给出的选项**:(A) 只 uses+attributed-to;(B) 字面 widen 全类型(uses/mitigates/detects/subtechnique-of/revoked-by/attributed-to);(C) 分流(事实边 vs 本体边分开)。
- **用户决策(原话)**:
  > "选第三项(分流),但收的事实边限定主语为威胁实体——uses/attributed-to(+OTX 的 targets);mitigates/detects 是防御侧事实,主语不在威胁本体里,现在不收;subtechnique-of/belongs-to-tactic 走 M1 本体边。你引用知识层 §4 做依据是对的,补这条主语判据。"
- **要点**:选项 C **+ 用户新增「主语威胁实体」判据**。事实边主语限 {intrusion-set, campaign, malware, tool};`mitigates` 主语=course-of-action、`detects` 主语=data-component(防御侧)→排除;`subtechnique-of`、technique→tactic→本体边。
- **落地**:`mitre_relationship.py` `_CTI_SOURCE_TYPES={intrusion-set,campaign,malware,tool}`、`_CTI_REL_TYPES={uses,attributed-to}`;`ontology_edges.py` 产 477 + 905 边。真实 bundle 事实边 17,295(+10,636 malware/tool)。

### 本轮决策②——indicator 落点〔用户拍板〕
- **原始问题**:去 indicator cap 后全量 indicator(单 pulse 实测达 20,090)放哪?直塞 Qdrant payload 会爆(`otx.py:18` cap 注释正为此)。
- **给出的选项**:(A) 独立 join 索引(全量进 raw + 新 index,payload 只留采样);(B) 字面去 payload metadata cap(全量塞 payload)。
- **用户决策(原话要点)**:选 A,并升级定性——
  > "indicator 已经属于 Knowledge Layer 的 Entity,而不是 Retrieval Layer metadata。全量 indicator 应进入独立索引(未来可自然演化为 Entity Registry 的 indicator 子集),Qdrant payload 仅保留少量检索投影字段(entity_ids、attack_ids 等)。否则 Retrieval Layer 会被迫承担知识层职责,且单 pulse 2 万 indicator 的 payload 膨胀与后续实体化方向相冲突。"
  > 给了 entity 形态示例 `{entity_id, type, value}` + occurrence map `{source_ids, actor_ids}`;结论"Indicator 是 Metadata 还是 Entity——按你现在的知识层设计它已被定义成 Entity,所以答案基本确定"。
- **落地**:`indicator_index.py`,`entity_id = indicator_ + sha256("{canonical_or_type}:{value}")[:16]`(exact 身份,无 fuzzy → 不受 D1/D2 门控);记录 `{entity_id, type:"indicator", indicator_type, canonical_type, value, ontology_id:null, source_ids[]}`;**`actor_ids` 留 schema 接口但不填**(需 M1 actor 解析,不瞎造)。229,883 entity。

### 本轮决策③——indicator 源类型→canonical 映射〔我提议,用户「继续做吧」总 go 下采纳,未逐字单独确认〕
- **触发**:真实全量(非 Phase 1 top-12)跑出 indicator `canonical=null` 占 33,209(14%),含 hostname(量极大)、URI、BitcoinAddress、FilePath、Mutex、CIDR、CVE、YARA、SSLCertFingerprint。
- **问题**:hostname/URI 本质即 domain/url,不映射则走不了 canonical join。
- **决策**:加 `hostname→domain`、`URI→url`(**源 type 仍逐字保留在 `indicator_type` 字段** → 非静默丢,Rule0 安全);其余无对应者保留 `canonical_type=null`。
- **落地**:`indicators.py` `_OTX_CANONICAL` 加两条;真实验证 null 33,209 → 984。

### 本轮决策④——稀疏 BM25 词表硬编码〔用户拍板〕
- **背景**:首次灌 v3 复用了 v2 词表(三处硬编码 `data/sparse_vocab.json`)。我最初措辞"会覆盖共享文件"被用户指为甩锅——实为路径未参数化的硬编码缺陷。
- **用户决策(原话)**:"修复硬编码问题。错误就是错误。"
- **落地**:`ingest.py` 加 `--sparse-vocab`;`bootstrap.vocab_path_for(collection)` 按 collection 自动配对 `sparse_vocab_{collection}.json`(eval 脚本零改动);`__init__`/`build_retrieval_stack` 同步;v2 不受影响。v3 用专属词表(43,857 token)重灌。

### 本轮范围界定〔我界定,非用户拍板——记录以免误判"丢信息"〕
- **W8 边界**:只产 mention(结构源 OTX/MITRE 从结构零推断 entity/relation mention + classification + provenance);**entity_id 解析=M1**(被 D1/D2 门控,未答→不做);**叙事(PDF)关系抽取=NLP**(文档 §4 自定为非 M0 deterministic);**不拆 `to_document`**(避免破坏现管线)。
- **W10 边界**:只把 M0 语料灌进 `cti_chunks_v3`,**不含 M2 检索层改动**。
- **未触及门控**:`DECISION-1…5` + D1/D2 门控的 M1 实体注册全部未做(M1 未起)。

### 本轮决策⑤——retrieved_at 语义统一〔用户拍板〕
- **背景**:rebuild 非确定性(`retrieved_at` 走墙钟 `utcnow`)→ git diff 永远脏、"变没变"不可见(Rule 0 隐性版本)。我第一版修法错误地把 mitre `retrieved_at` 锚到 STIX `modified`(那是**源**的修改时间,不是**我们**的取数时间,且与 `metadata.last_modified` 重复)——用户指出语义错。
- **用户拍板(4 条)**:① mitre `retrieved_at` 改锚 RawStore `fetched_at`(非 STIX modified);STIX modified 留 `metadata.last_modified` 别动。② pdf 纳入版本化 RawStore,`retrieved_at = 入库 fetched_at`;存量 PDF 无入库事件 → **固定 sentinel**(不用 mtime,破确定性)。③ 口径统一:所有源 `retrieved_at = RawStore fetched_at`,源内容时间归 `metadata.last_modified`。④ 不新建字段。
- **语义定论**:`retrieved_at` = **我们何时取的**(our fetch);`metadata.last_modified` = **源何时改的**(source modified);pipeline rebuild 时间不存。
- **落地**:`store/raw_store.py` 加 `SENTINEL_FETCHED_AT` + `parse_fetched_at`;删 `connectors/_stix.py`;mitre_attack/mitre_relationship/pdf_reports 连接器加 `fetched_at` 参数(默认 sentinel),`retrieved_at=self._fetched_at`;seed_mitre/seed_mitre_relationships 从 `RawStore.versions("mitre","enterprise-attack")` 读 fetched_at 传入;**mitre_relationship metadata 补 `last_modified`**(原本缺,否则源时间丢)。验证:mitre 技术+关系 seed 两次字节一致,`retrieved_at`=bundle fetched_at(2026-04-25)、`last_modified`=各对象 STIX modified。
- **未尽 → 已由本轮决策⑦解决**:pdf `retrieved_at=sentinel` 已落;**PDF 正式入版本化 RawStore 已做**(CAS BlobStore + JSON manifest,见决策⑦,commit `1acb661`)。

### 本轮决策⑥——RawStore 原子写〔补记,commit `13dae2f`〕
- **问题**:`raw_store.py` 原 `write` 直写目标文件,写到一半崩溃/断电会留半截文件 → 损坏 raw。raw 是永久证据底,损坏不可逆(Rule 0)。
- **修法**:写同目录临时文件 → `flush` + `os.fsync`(落盘)→ `os.replace`(原子重命名替换)。崩溃后要么旧版完整、要么新版完整,绝不留半截。
- **落地**:`store/raw_store.py`(+13 行);`tests/unit/test_raw_store.py` +68 行(S0-1..4:正常写入、覆盖前旧内容保全、tmp 不残留、中断语义)。
- **CI**:commit 时 `make ci` 全绿。

### 本轮决策⑦——PDF 正式入版本化 RawStore(CAS BlobStore)〔补记,commit `1acb661`;接决策⑤未尽〕
- **问题(决策⑤遗留)**:RawStore 存 JSON,而 PDF 是二进制,"raw 表示"待定 → PDF 原文一直没进版本化 raw。
- **修法**:新建内容寻址 BlobStore `store/blob_store.py`——字节按 `sha256` 寻址、immutable、原子写、**读时校验**(完整性不符抛 `BlobIntegrityError`);`ingest/ingest_pdf.py`(`ingest_pdf`/`backfill_pdfs`):**先 `blob.put` 落字节,后写 manifest** `{kind:"blob_ref", sha256, size, content_type, filename}` —— 顺序防悬空引用(C2)。
- **落地**:`blob_store.py`(+76)、`ingest_pdf.py`(+57)、`tests/unit/test_blob_store.py`(+64)、`tests/unit/test_ingest_pdf.py`(+124)。
- **真实数据验证**:14 份 PDF → 13 blob(2 份 Microsoft 报告字节相同,内容寻址自动去重);`retrieved_at=sentinel`(存量 PDF 无入库事件);A1–A7 verbatim 验。
- **CI**:commit 时 `make ci` 全绿(660 passed)。

### 早期操作决策(完整性补记)
- 新建 worktree `feat/optimization`(base `cd481c5`),主仓库不 checkout(铁律);删除根目录 4 个未跟踪残留(`certification_*`/`query_set_v3_sample` 等,smoke/aborted 实验产物,用户确认删)。

---

## 10. v3 重认证结果(2026-06-15,全 DeepSeek + GPU)

**口径**:本次 `cti_chunks_v3` vs 基线 `cti_chunks_v2`(认证 `2026-06-11`,亦 DeepSeek 标注、同 n、同检索机制)——**唯一大变量 = 语料 v2→v3**。eval-all 四阶段**零 Groq**:阶段 1 `--provider deepseek`、阶段 2 默认 `hybrid`(无 LLM 调用)、阶段 3 `--gen-provider deepseek`(绕开 Groq TPD 100k)、阶段 4 render。证据:`certification_full_deepseek_2026-06-15T02-55-40Z.json` + `capabilities_summary.json` + `attribution_v3_results.json` + `ragas_v3_results.json`。

| 能力 | 指标 | 基线 v2(06-11) | v3(本次) | 门控 |
|---|---|---|---|---|
| [1] technique extraction | CTI-ATE Micro-F1 (n=47) | 0.6703 (P .746 / R .609) | **0.8582** (P .940 / R .789) | ≥0.65 → PASS |
| [2] actor attribution | CTI-TAA plausible (n=50) | 0.68 (correct .66) | **0.76** (correct .68) | ≥0.5 → PASS |
| [3] heterogeneous retrieval | hit@10 各类 | precise/semantic/fuzzy=1.0; rel_direct/otx_malware=0.8; otx_actor=0.286 | **与基线持平** | (无门控) |
| [4] generation grounding | RAGAS faithful / relevancy (n=14) | 0.9113 / 0.8200 (Groq gen) | 0.9506 / 0.8547 (**DeepSeek gen**) | (无门控) |

- **[1] ATE +0.19 F1、[2] TAA plausible +0.08 = M0 v3 语料增益**(typed indicators + 10,636 条 malware/tool→technique 能力边等);P/R 同步上升,非 precision-recall 互换。
- **[3] 检索 hit@k 与基线持平**:检索机制未改(M2 未做),这些类别要么已饱和(=1.0)、要么基于硬标识(pulse_id 口径不变),语料内容增益不移动单目标 hit@k。
- **[4] RAGAS 不同口径,不可归因于语料**:v3 生成器=`deepseek-chat`、基线=`groq/llama-3.3-70b`,且评判亦 DeepSeek(**自评偏置**)→ 此项数字仅作 DeepSeek 路径记录,**不与 Groq 基线直接比较**。artifact 已记 `generator_provider=deepseek`。
