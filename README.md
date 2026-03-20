"""README for AI Spider."""
# 🕷️ AI Spider - 智能爬虫平台

基于DAG引擎的AI驱动爬虫系统，支持双模式爬取和代码验证迭代。

## ✨ 特性

- **双模式爬取引擎**:
  - **SmartScraper模式**: 用户描述需求 → LLM直接从HTML提取结构化数据
  - **CodeGenerator模式**: 生成Python爬虫代码 → 4轮自动验证迭代(语法→执行→Schema→语义)

- **DAG执行引擎**: 参考ScrapeGraphAI架构，原子节点 + 工作流图
- **任务调度系统**: Redis队列，Worker自注册，优先级/重试/超时控制
- **完整管理后台**: 项目/任务/Worker/数据管理，实时监控
- **安全沙箱**: 代码隔离执行，防止恶意代码

## 🏗️ 架构

```
src/
├── core/           # 配置、模型、数据库
├── engine/         # 核心引擎 (DAG)
│   ├── nodes/      # 原子节点 (Fetch, Parse, Extract, Generate, Validate)
│   ├── graphs/     # 工作流图 (SmartScraper, CodeGenerator, DeepCrawler)
│   ├── sandbox.py  # 安全沙箱
│   └── prompts/    # LLM提示模板
├── scheduler/      # 任务调度 (Redis队列, Worker管理)
├── api/            # FastAPI接口
└── web/            # 前端界面
```

## 🚀 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 设置LLM API密钥等
```

### 3. 启动服务
```bash
python main.py
# 或
uvicorn src.api.app:app --host 0.0.0.0 --port 8900
```

### 4. 访问界面
- 用户端: http://localhost:8900/
- 管理后台: http://localhost:8900/admin

## 📖 使用指南

### 创建项目
1. 点击"新建项目"
2. 选择模式:
   - **代码生成**: 生成可编辑的Python爬虫代码
   - **智能提取**: LLM直接提取数据，无需代码
3. 输入目标URL和需求描述
4. AI自动生成代码或提取数据

### 测试与部署
- **测试**: 在代码编辑器中测试爬虫
- **对话**: 与AI对话修改代码
- **部署**: 配置任务参数，部署到Worker执行

### 管理后台
- **仪表盘**: 系统统计概览
- **任务管理**: 查看/操作所有任务
- **Worker监控**: 查看Worker状态和资源
- **系统日志**: 查看实时日志

## 🔧 配置

### LLM配置
```env
LLM_PROVIDER=deepseek
LLM_API_KEY=your-api-key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com/v1
```

### Redis配置
```env
REDIS_URL=redis://127.0.0.1:6379/2
```

### 数据库
默认使用SQLite: `data/spider.db`

## 📊 API文档

启动服务后访问: http://localhost:8900/docs

主要API端点:
- `GET /api/v1/projects` - 项目列表
- `POST /api/v1/projects` - 创建项目
- `POST /api/v1/tasks` - 创建任务
- `GET /api/v1/workers` - Worker列表
- `GET /api/v1/data` - 数据列表

## 🧪 代码验证流程

CodeGenerator模式采用4轮验证:

1. **语法检查**: `ast.parse` 验证Python语法
2. **执行检查**: 沙箱执行，验证代码能运行
3. **Schema检查**: 验证输出为 `list[dict]` 格式
4. **语义检查**: LLM判断输出是否匹配用户需求

每轮失败自动重试修复，最多3次。

## 🤝 贡献

欢迎提交Issue和PR!

## 📄 许可证

MIT
