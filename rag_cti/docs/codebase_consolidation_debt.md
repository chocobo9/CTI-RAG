# 鍏ㄦ爤鏀跺彛鍊哄璁?鈥?agent loop 涔嬪

> **鑼冨洿**锛歨arness(`knowledge/` agent loop)涔嬪鐨勫瓙绯荤粺銆俬arness 鏈韩瑙?`harness_audit_handoff.md`銆?> **鏉ユ簮**锛? 涓苟琛屽瓙瀹¤(retrieval / generation+entry / connectors+ingest+store / preprocess+embeddings+eval锛?> + 涓诲璁″楂樹弗閲嶅害椤圭殑澶嶆牳銆?> **澶嶆牳鏍囨敞**锛歚[鉁撴牳瀹瀅` = 涓诲璁′翰鑷?grep/read 纭锛沗[~瀛愪唬鐞哴` = 瀛愪唬鐞嗘姤鍛婏紝**鏈嫭绔嬪鏍革紝鍔ㄦ墜鍓嶉渶鑷獙**銆?> **缁撹**锛氬悓涓€鐥呮牴锛?鍔犳柊瀹炵幇涓嶉€€鏃?/ 涓嶆娊鍏叡"锛?*涓嶆鍦?agent loop锛屽叏鏍堝垎甯?*锛涙渶闆嗕腑鍦?LLM provider 璋冨害灞備笌鏁版嵁鎺ュ叆灞傘€?
---

## A. LLM provider 璋冨害灞?鈥斺€?agent loop 涔嬪鏈€璇ュ厛鏀跺彛

- **A1 `[鉁撴牳瀹瀅` limiter 鍐欎簡鍗存病鎺ヤ富绛旀璺緞銆?* `generator._call_llm`(`generation/generator.py:162`)鐩存帴 `client.chat.completions.create`锛?*鏃?`.slot()`**锛沗knowledge/chat_fn.py`(judge/composer)鍚屾牱鏃?limiter銆俫rep 纭涓ゆ枃浠堕浂 `get_limiter`/`.slot()`銆傗啋 `generation/limiter.py` 鏂囨。鑷О鍏滃簳"every LLM path"锛屼絾涓诲悎鎴?+ judge 涓嶅崰 slot锛宎dmission control 鏈夌┖娲炪€?*涓ラ噸搴︼細楂樸€?*
- **A2 `[鉁撴牳瀹瀅` 鍚屼竴 DeepSeek provider 涓ゅ client 鏋勯€犮€?* `bootstrap.build_deepseek_client`(`bootstrap.py:146`)= 瑁?`openai.OpenAI`锛堜粎 SDK `max_retries`锛屾棤 429 TPD/TPM 鍒嗙被銆佹棤 limiter锛夛紱`knowledge/model_factory.build_model`(`model_factory.py:35`)= `langchain ChatOpenAI` + `_LimitedChatModel`銆俢lient.py 鐨勭簿缁?429 鍒嗙被鍙寕 Groq/Ollama 娆＄骇璺緞銆?*淇瀛愪唬鐞嗗畾鎬?*锛欴eepSeek 瑁?client 鏄?`bootstrap.py:149` docstring 鑷堪鐨?*鏈夋剰 fast-fail**锛堜笂灞?`FallbackChatClient` 鍋氶噸璇曟潈濞侊級锛屽睘"涓ゅ骞跺瓨"鑰岄潪"瑁稿鐤忔紡"銆?*涓ラ噸搴︼細涓?楂橈紙缁撴瀯骞跺瓨灞炲疄锛屼絾鏈夎璁＄悊鐢憋級銆?*
- **A3 `[鉁撴牳瀹瀅` DeepSeek endpoint/model 鐪熺浉婧愬垎鍙夈€?* `model_factory.py:42` 纭紪鐮?`base_url="https://api.deepseek.com"` + `model="deepseek-chat"` 瀛楅潰閲忥紝鑰?`bootstrap.py` 宸叉湁 `DEEPSEEK_BASE_URL` 甯搁噺锛坄build_deepseek_client` 鐢ㄧ殑灏辨槸瀹冿級+ `DEEPSEEK_DEFAULT_MODEL`銆傛敼绔偣/涓绘ā鍨嬩細婕忔帀 model_factory銆?*涓ラ噸搴︼細涓€?*
- **A4 `[~瀛愪唬鐞哴` hyde 涓?query_rewrite 鍚勮嚜鎵嬫悡 provider dispatch銆?* 鎶ュ憡锛歚hyde.py:44-60` 鈮?`query_rewrite.py:105-120`锛堟敞閲婅嚜璁?"Mirror HyDE's client handling"锛夛紝`groq/ollama vs anthropic` 鍒嗘敮 + model 閫夋嫨涓や唤鎵嬪啓锛屼笖閮界敤 `hasattr(...,"chat")` 鍚彂寮?*缁曡繃** `client.build_llm_client`(宸茶繑鍥?`(provider, client)`)銆備袱涓粯璁ゅ紑鍚€侀兘鍦ㄤ富妫€绱㈣矾寰勩€?*涓ラ噸搴︼細楂橈紙鏈鏍革級銆?*

> A1鈥揂4 鍚屼竴鐥呮牴锛欴eepSeek/Groq/Ollama/Qwen 鐨?client 鏋勯€?+ retry + limiter 鍒嗘暎鍦?`client.py` / `bootstrap.py` / `model_factory.py` / `hyde.py` / `query_rewrite.py` **浜斿鍚勫啓鍚勭殑**銆?
## B. 鏁版嵁鎺ュ叆灞傦紙connectors / ingest / scripts锛?
- **B1 `[鉁撴牳瀹瀅` `fetch_to_raw` 姝绘娊璞°€?* 閫氱敤 raw-ingest 鍏ュ彛锛坄ingest/raw_ingest.py:28`锛夛紝grep 鍏?repo **鍙懡涓?瀹氫箟 + 娴嬭瘯 + M0 鏂囨。锛岄浂鐢熶骇璋冪敤**锛況efetch 鑴氭湰鍚勮嚜鎵嬪啓 `fetch鈫抯tore.write`銆?*涓ラ噸搴︼細楂樸€?*
- **B2 `[鉁撴牳瀹瀅` WHOIS 绠＄嚎鍗婅縼绉汇€?* VT/pDNS 鏄共鍑€涓ゆ寮忥紙refetch-raw + `project_*.py`锛夛紱WHOIS 鍙湁 `removed WHOIS direct-processed fetch script` + `refetch_whois_raw.py`锛?*鏃?`project_whois.py`**锛坙s 纭锛夆啋 WHOIS chunk 鎷夸笉鍒?VT/pDNS 閮芥湁鐨勫熀纭€璁炬柦瀹炰綋/杈癸紝鍐欒繘 RawStore 鐨?whois raw 涓嶈鎶曞奖娑堣垂銆?*涓ラ噸搴︼細楂樸€?*
- **B3 `[~瀛愪唬鐞哴` `project_vt.py` 涓?`project_pdns.py` copy-paste 鍙岃優鑳?*锛堢粨鏋勫叏鍚岋紝浠?connector/loader/source 瀛楅潰閲忎笉鍚岋級銆傛瘡鍔犱竴涓熀纭€璁炬柦婧愬啀澶嶅埗涓€浠借剼鏈€?*涓€?*
- **B4 `[~瀛愪唬鐞哴` 涓や釜 raw 蹇収 loader 浜掍负澶嶅埗涓旂粫寮€ RawStore 璇?API銆?* `vt_projection.load_vt_raw_payloads`(`:47`)鈮?`pdns_projection.load_pdns_raw_dir`(`:67`)锛屾墜鍒ㄧ洰褰曡€岄潪鐢?`RawStore.iter_latest`銆?*涓€?*
- **B5 `[~瀛愪唬鐞哴` malware family 鎶藉彇涓や唤鐩稿悓瀹炵幇** `otx._malware_family_names`(`:78`)鈮?`ingest/normalize._otx_family_names`(`:103`)銆?*涓€?*
- **B6 `[~瀛愪唬鐞哴` VT 婧愯韩浠?`virustotal` vs `vt` 涓夊鍏滃簳鍒嗗弶**锛坄virustotal.py:116` / `project_vt.py:32` / `normalize.py:44` 鍚屽涓ら敭 / `normalizers.py:8` 鍙 virustotal锛夈€?*涓€?*
- **B7 `[~瀛愪唬鐞哴` `whoxy.py` 澶嶅埗 `base.py` 鐨?`_RETRY_KWARGS` 骞堕噸閫?HTTP 鍩哄骇**锛坬uery-param 閴存潈鏃犳硶澶嶇敤 `HttpConnector`锛夈€?*浣庛€?*
- **B8 `[~瀛愪唬鐞哴` pDNS 鎶撳彇鏃?connector锛宍refetch_pdns_raw.py:32` 鍙嶅悜 import OTX 绉佹湁甯搁噺 `_OTX_BASE`銆?* **浣?涓€?*

## C. preprocess / 瀹炰綋 id

- **C1 `[~瀛愪唬鐞哴` entity_id 鏂规纰庣墖鍖栵紙褰卞搷姝ｇ‘鎬э紝浼樺厛楠岋級銆?* 閾搁€犲垎鏁ｅ湪 `indicator_index` / `entity_registry` / `chunking` / `facts`锛岃€?`facts.entity_type`(`facts.py:122`)闈犵‖缂栫爜 `_TYPE_PREFIXES` **瀛楃涓插墠缂€鍙嶆帹绫诲瀷**锛屽繀椤讳笌姣忎釜閾搁€犵偣鎵嬪伐鍚屾銆傛洿鐢氾細鍚屼竴 indicator 鏈?*涓ゅ绔炰簤 id 鏂规**锛堥€氱敤 resolver `indicator_orphan_<hash(name)>` vs `indicator_index` `indicator_<hash(kind:value)>`锛夛紝`infra_relations.py:8` docstring 鑷蹇呴』缁曞紑閫氱敤 resolver銆?*涓紙浣嗚Е鍙婃纭€э級銆?*
- **C2 `[~瀛愪唬鐞哴` `_attack_id`锛圫TIX external_id 鎻愬彇锛夊鍒?5 澶?*锛歚ontology_nodes.py:40` / `ontology_edges.py:18` / `mitre_attack.py:74` / `mitre_relationship.py:75` / `normalize.py:172,188`銆傛棤鍏变韩 MITRE-STIX 瑙ｆ瀽妯″潡銆?*涓€?*
- **C3 `[~瀛愪唬鐞哴` seeding 涓ゅ杩戦噸澶嶅叆鍙?* `seed_connector_to_jsonl`(`seeding.py:51`)/ `seed_connector_with_projection`(`:94`)鏁存 drain 寰幆澶嶅埗锛屽悗鑰呰繕鎵嬪伐閲嶅疄鐜?`BaseConnector.fetch_documents` 鐨?skip 閫昏緫銆?*涓€?*
- **C4 `[~瀛愪唬鐞哴` OTX 鏈?2-3 鏉″苟琛?ingestion 娴佹按绾夸骇鍚屼竴浠?`otx.jsonl`**锛坄removed OTX direct-processed fetch script` 鏃?projection / `rebuild_otx_jsonl.py` 鎵嬫妱 projection / `removed OTX pulse-id direct-processed fetch script` 鑷悡 chunk锛夛紝payload 涓嶄竴鑷淬€?*涓€?*

## D. retrieval锛堥櫎 A4 澶栵級

- **D1 `[~瀛愪唬鐞哴` `pipeline.py:99` 鐢?`isinstance(self._retriever, QueryRewriteRetriever)` 鐗瑰垽鍏蜂綋瀛愮被**锛屾墦鐮?`RetrieverProto` 鎶借薄锛屽啀鍔犱竴涓?鑳界悊瑙ｆ煡璇?鐨?retriever 灏卞緱鏀?Pipeline銆?*涓€?*
- **D2 `[~瀛愪唬鐞哴` ATT&CK 鐖?瀛愬叧绯?3 濂楀疄鐜?*锛坄ontology_expand.expand_attack_ids` / `set_metrics.normalize_id` / `retrieval_metrics._is_match`锛夛紝绠楁硶鍒绘剰涓嶅悓锛屽鍦?eval锛涙蹇甸噸澶嶈€岄潪鍙満姊板悎骞躲€?*浣庛€?*

## E. 姝讳唬鐮?/ 姝婚厤缃紙浣庯級

- **E1 `[~瀛愪唬鐞哴` `TaskType.REPORT` + `config.groq_report_model`** 鏃犱换浣?`model_for(REPORT)` 璋冪敤鐐广€?- **E2 `[~瀛愪唬鐞哴` `config.vt_api_key`** 鑷堪 reserved锛岃繍琛岃矾寰勬棤娑堣垂鑰呫€?- **E3 `[~瀛愪唬鐞哴` `ChunkStrategy.FIXED` / `_fixed_chunks`** 浠呮祴璇曞彲杈撅紙鏍?ablation baseline锛夈€?- **E4 `[~瀛愪唬鐞哴` `query_rewrite_parallel_fanout_enabled`(`config.py:139`, 榛樿 True)** 瀹炵幇浠庝笉璇诲畠锛屽苟琛岀敱 `max_parallel_subqueries` 鎺?鈫?鏂囨。鍖栫殑 off-switch 娌℃帴绾裤€?- **E5 `[~瀛愪唬鐞哴` `FixedRouter` 鍦ㄧ敓鎴愯矾寰勮繎 vestigial**锛氶€夊嚭鐨?model 鍚嶈 `FallbackChatClient` `pop` 鎺夛紝鍙繘 trace 涓嶅喅瀹氭ā鍨嬨€?
## 瀛愪唬鐞嗘槑纭帓闄ょ殑锛堥潪缂洪櫡锛岄伩鍏嶈鎶ワ級
- fusion 澶嶇敤姝ｅ父锛坄hybrid_retriever` 涓?`query_rewrite` 鍚岃蛋 `fusion.reciprocal_rank_fusion`锛夈€?- IOC/ATT&CK 姝ｅ垯鍗曟簮澶嶇敤鍋ュ悍锛坄query_normalize`/`constraint_extract`/`agentic_effort` 閾撅級銆?- store 涓夊眰鑱岃矗娓呮櫚銆佹棤閲嶅鍐欏叆璺緞銆?- MITRE 涓?connector锛堣妭鐐?vs 杈癸級鏄笉鍚屼骇鐗┿€?- `set_metrics` 鏁呮剰涓嶅鐢?`retrieval_metrics._is_match`锛堜功闈㈢悊鐢憋紝璇箟涓嶅悓锛夈€?- `answer_single_shot` 鏄湁鎰忎繚鐣欑殑 baseline/fallback public API锛岄潪姝讳唬鐮併€?- embeddings銆乷bservability/tracing銆乧ontext_builder銆乸rompts 鍗曞疄鐜板仴搴峰鐢ㄣ€?
---

## 鍏冪粨璁?
鐢ㄦ埛闂?agent loop 涔嬪杩樻湁娌℃湁绫讳技闂" 鈫?**鏈夛紝鑰屼笖鏄悓涓€涓梾鏍圭殑鍏ㄦ爤鐗?*銆傛渶闆嗕腑涓ゅ锛?1. **LLM provider 璋冨害灞?*锛圓1鈥揂4锛夛細5 澶勫悇鍐?client/retry/limiter锛宭imiter 娌℃帴涓荤瓟妗堣矾寰勩€?2. **鏁版嵁鎺ュ叆灞?*锛圔1鈥揃8 / C3鈥揅4锛夛細閫氱敤鎶借薄锛坄fetch_to_raw`銆乣seed_connector_with_projection`锛夊啓濂藉嵈琚剼鏈粫杩囧鍒讹紝WHOIS 鍗婅縼绉汇€?
`[鉁撴牳瀹瀅` 鐨?6 鏉★紙A1/A2/A3/B1/B2 + limiter grep锛夋槸浜嬪疄锛沗[~瀛愪唬鐞哴` 鐨勫叾浣欓」鏄瓙浠ｇ悊鎶ュ憡锛?*鏈粡涓诲璁＄嫭绔嬪鏍?*锛屽疄鏂藉墠闇€閫愭潯鑷獙銆?
