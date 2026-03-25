# AI Spider SDK — 内网集成指南

## 安装

```bash
pip install httpx
```

把 `ai_spider_client.py` 复制到你的项目，或者直接用 HTTP 调用。

## 快速开始

### Python SDK

```python
from ai_spider_client import SpiderClient

# 连接
client = SpiderClient(
    base_url="https://rthe525.top/spider",  # 或内网 http://192.168.x.x:8901
    api_key="sk-9295a4b98ce9f35b6e65e1e60535dfd0",
)

# 一键爬取（创建项目 → AI生成代码 → 测试 → 返回数据）
data = client.quick_crawl(
    url="https://quotes.toscrape.com/",
    fields="quote,author,tags",
)
# => [{"quote": "...", "author": "...", "tags": "..."}, ...]
```

### 分步调用

```python
# 1. 创建项目（异步，立即返回）
proj = client.create_project(
    target_url="https://movie.douban.com/top250",
    description="电影名称,评分,评价人数",
    name="豆瓣Top250",
)
print(proj["id"])  # "98c17b4bce54"

# 2. 等待 AI 生成爬虫代码
proj = client.wait_for_generation(proj["id"], timeout=300)
print(proj["status"])  # "generated" or "tested"

# 3. 运行测试
result = client.test_project(proj["id"], timeout=120)
print(f"Items: {len(result['output'])}")
print(result["output"][:3])

# 4. 查看/修改代码
proj = client.get_project(proj["id"])
print(proj["code"])

# 5. 手动替换代码
client.update_code(proj["id"], """
async def crawl(url, config):
    import httpx
    async with httpx.AsyncClient() as c:
        r = await c.get(url)
    # your custom logic...
    return [{"title": "..."}]
""")
```

### JS 渲染站点

```python
# 36kr、富途等需要 JS 渲染的站点
data = client.quick_crawl(
    url="https://36kr.com/newsflashes",
    fields="标题,摘要,发布时间",
    use_browser=True,  # 启用 Playwright
)
```

### 分页爬取

```python
# CICC 证券列表（15页，7000+条）
data = client.quick_crawl(
    url="https://www.cicc.com/business/single_135_152.html",
    fields="证券代码,证券简称,保证金比例",
    use_browser=True,
    enable_pagination=True,
)
```

### 命令行

```bash
# 一键爬取
python ai_spider_client.py --server https://rthe525.top/spider \
  --key sk-xxx crawl "https://quotes.toscrape.com/" "quote,author,tags"

# 列出项目
python ai_spider_client.py --key sk-xxx list

# 测试项目
python ai_spider_client.py --key sk-xxx test 98c17b4bce54
```

## 纯 HTTP 调用（curl / 任何语言）

所有接口都是标准 REST，不需要 SDK：

```bash
API="https://rthe525.top/spider"
KEY="sk-9295a4b98ce9f35b6e65e1e60535dfd0"

# 创建项目
curl -X POST "$API/api/v1/projects" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"test","description":"title,price","target_url":"https://example.com","mode":"code_generator"}'

# 查看状态
curl "$API/api/v1/projects/{id}" -H "X-API-Key: $KEY"

# 运行测试
curl -X POST "$API/api/v1/projects/{id}/test" \
  -H "X-API-Key: $KEY" \
  -H "Content-Type: application/json" -d '{}'

# 列出数据
curl "$API/api/v1/data?project_id={id}" -H "X-API-Key: $KEY"

# 导出 CSV
curl "$API/api/v1/data/export/csv?project_id={id}" -H "X-API-Key: $KEY" -o data.csv
```

## API 完整列表

### 核心接口

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/projects` | 创建项目（触发AI代码生成） |
| `GET` | `/api/v1/projects` | 列出所有项目 |
| `GET` | `/api/v1/projects/{id}` | 获取项目详情（含code） |
| `PUT` | `/api/v1/projects/{id}` | 更新项目配置 |
| `PUT` | `/api/v1/projects/{id}/code` | 保存爬虫代码 |
| `POST` | `/api/v1/projects/{id}/test` | 运行测试爬取 |
| `POST` | `/api/v1/projects/{id}/refine` | AI对话优化代码 |
| `DELETE` | `/api/v1/projects/{id}` | 删除项目 |

### 任务调度

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/v1/tasks` | 创建定时任务 |
| `GET` | `/api/v1/tasks` | 列出任务 |
| `POST` | `/api/v1/tasks/{id}/cancel` | 取消任务 |
| `POST` | `/api/v1/tasks/{id}/retry` | 重试任务 |
| `GET` | `/api/v1/tasks/{id}/runs` | 查看运行历史 |

### 数据

| Method | Path | 说明 |
|--------|------|------|
| `GET` | `/api/v1/data?project_id=X` | 查看爬取数据 |
| `GET` | `/api/v1/data/stats` | 数据统计 |
| `GET` | `/api/v1/data/export/json` | 导出 JSON |
| `GET` | `/api/v1/data/export/csv` | 导出 CSV |

### 认证

所有接口需要 `X-API-Key` header。获取方式：
1. 管理后台创建用户
2. `POST /api/v1/auth/login` 获取 api_key
3. 或使用管理员 key

## 网络配置

| 访问方式 | 地址 | 说明 |
|----------|------|------|
| 公网 HTTPS | `https://rthe525.top/spider` | 经 nginx 反代 |
| 内网直连 | `http://{内网IP}:8901` | 无 nginx，更快 |
| 本机 | `http://127.0.0.1:8901` | 最快 |

如果内网其他机器需要访问，确保防火墙放行 8901 端口。
