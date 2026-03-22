# AI Spider × Wukong 合并计划

## 目标
将 Arachne/wukong 的生产级能力移植到 AI Spider，保留 AI Spider 的 LLM 引擎作为核心。

## 源代码位置
- AI Spider: `/root/.openclaw/workspace/ai-spider/`
- Wukong模块: `/www/arachne/backend/wukong/`

## 移植模块（按优先级排序）

### P0: 代理管理 (wukong/proxy/ → src/engine/proxy.py)
- 当前: AI Spider只有基础代理池(~80行)
- 目标: 
  - ProxyManager: 轮询/随机策略、代理质量检测、失败自动切换
  - VolcanoProxy: 火山引擎住宅代理支持(session管理、自动刷新)
  - UserAgent轮换: 从wukong/proxy/user_agent.py移植UA池
  - Header伪装: 从wukong/auth/header_token.py移植
- 文件: `src/engine/proxy_manager.py` (新建，替换原proxy.py)
- 注意: 保留AI Spider现有的proxy pool数据库模型，扩展功能

### P1: 持久化去重 (wukong/dedup/ → src/engine/dedup.py) 
- 当前: AI Spider只有内存哈希去重(~50行)
- 目标:
  - MemoryDeduper: 保留现有，加LRU淘汰
  - RedisDeduper: Redis集合去重，支持TTL过期
  - BloomFilterDeduper: 布隆过滤器，大规模场景内存友好
  - RotationDeduper: 滚动窗口布隆过滤器
- 文件: `src/engine/dedup/` (目录化)
- 依赖: redis (已有), pybloom_live (新增)

### P2: 流控限速 (wukong/cms/ → src/engine/rate_limiter.py)
- 当前: AI Spider只有简单sleep(DEFAULT_DELAY)
- 目标:
  - SlidingWindowCounter: 滑动窗口QPS控制
  - DimensionLimiter: 按域名/IP维度限速
  - PressureController: 根据响应时间自动调整并发
- 文件: `src/engine/rate_limiter.py` (新建)
- 集成点: fetch node调用前检查限速

### P3: 监控指标 (wukong/metric/ → src/engine/metrics.py)
- 当前: AI Spider无监控
- 目标:
  - Prometheus指标: 请求数/成功率/延迟/数据量
  - PushGateway推送
  - 任务级维度上报
- 文件: `src/engine/metrics.py` (新建)
- 依赖: prometheus_client (新增)

### P4: 存储增强 (wukong/storage/ → src/sinks/)
- 当前: AI Spider有local/s3/kafka/sqlite 4种sink
- 目标:
  - 增加 Parquet格式 Writer/Reader
  - 增加 压缩支持 (gzip/zstd/snappy)
  - 增加 文件分片 (按时间/大小自动切分)
- 文件: 扩展现有 `src/sinks/` 模块
- 依赖: pyarrow (新增), zstandard (新增)

## 集成点
1. `src/engine/nodes/fetch.py` — 接入代理管理器 + 限速器 + 指标上报
2. `src/engine/nodes/extract.py` — 接入去重
3. `src/sinks/` — 接入新存储格式
4. `src/api/v1/` — 新增代理管理API、监控API
5. `src/core/config.py` — 新增配置项

## 不移植的部分
- wukong/spiders/common_crawl — 特定爬虫，不通用
- wukong/extract/parse.py — 站点特化解析器(futu/tiger/naver)，AI Spider用LLM替代
- wukong/mq/kafka — AI Spider已有kafka_sink
- wukong/cache — AI Spider用Redis

## 原则
1. 适配AI Spider的异步架构(async/await)，wukong部分是同步的需要改
2. 保持AI Spider的模块风格和命名规范
3. 新增依赖要可选(extras_require)，核心功能不强依赖
4. 所有代码注释用中文
