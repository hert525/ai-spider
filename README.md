# 🕷️ AI-Spider

**AI-powered distributed web crawler** — describe what you need in natural language, AI generates and optimizes the crawler code.

## ✨ Features

- 🗣️ **Natural Language → Crawler**: Describe your scraping needs, AI generates the code
- 🔄 **Iterative Optimization**: Test → Review → Feedback → AI refines → Repeat until perfect
- 🌐 **Distributed Execution**: Scale across multiple nodes with Redis-based task queue
- 🎯 **Smart Extraction**: LLM-powered data extraction with auto-schema generation
- 📊 **Web Dashboard**: Manage crawlers, view results, monitor tasks
- 🔌 **Pluggable**: Support multiple LLM backends (DeepSeek, OpenAI, Gemini, local Ollama)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                   Web Dashboard                  │
│         (Create / Test / Monitor Crawlers)        │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│                   API Server                     │
│              (FastAPI + WebSocket)                │
└──────┬───────────────┬───────────────┬──────────┘
       │               │               │
┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│  AI Engine  │ │  Sandbox    │ │  Task Queue │
│ (Code Gen)  │ │  (Testing)  │ │  (Redis)    │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────┬───────┘        ┌──────▼──────┐
               │                │  Workers    │
        ┌──────▼──────┐        │  (Distributed│
        │  Crawler    │        │   Execution) │
        │  Runtime    │        └─────────────┘
        └─────────────┘
```

## 🔄 Workflow

```
1. User describes need: "爬取豆瓣Top250电影的名称、评分和简介"
                              ↓
2. AI generates crawler code (Python/Scrapy)
                              ↓
3. Sandbox test run → Preview results (first 5 items)
                              ↓
4. User reviews: "评分需要转成数字，还要加上导演信息"
                              ↓
5. AI modifies code → Re-test → Preview
                              ↓
6. User confirms → Deploy to distributed workers
                              ↓
7. Full crawl → Results stored → Export (JSON/CSV/DB)
```

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/hert525/ai-spider.git
cd ai-spider

# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your LLM API key and Redis config

# Run
python -m src.api.server
```

## 📦 Tech Stack

- **Backend**: Python 3.11+, FastAPI, WebSocket
- **AI**: LiteLLM (multi-provider), Jinja2 (prompt templates)
- **Crawler Runtime**: Playwright (JS rendering), httpx (static), parsel (parsing)
- **Distributed**: Redis (task queue + dedup), Celery workers
- **Storage**: PostgreSQL (metadata), file system (results)
- **Frontend**: Vue 3 + Tailwind CSS

## 🛠️ Development

```bash
# Run tests
pytest tests/

# Run in dev mode
python -m src.api.server --reload --debug
```

## 📄 License

MIT
