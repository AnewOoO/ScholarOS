# ScholarOS

ScholarOS 是一个本地研究工作台，覆盖四段流程：

```text
推荐论文 / 构建论文库
        ↓
精读论文 / 总结翻译
        ↓
代码解读 / 论文代码对齐
        ↓
论文写作 / 研究输出
```

## Agents

- **Paper Builder Agent**：用户输入研究方向后，自动扩展关键词，检索 arXiv、OpenReview、Papers with Code、Hugging Face Papers，按相关度、代码可用性、引用/热度和时间排序，并解释推荐理由。
- **Paper Reading Agent**：根据用户 prompt、论文库摘要或 arXiv PDF 片段生成精读回答，输出问题定义、方法、实验和局限。
- **Code Interpreter Agent**：读取 GitHub 仓库或本地目录，分析项目结构，定位训练入口、配置、核心方法、评估脚本，生成运行命令，并做论文-代码对齐。
- **Paper Writing Agent**：基于论文库生成 Related Work、研究 gap、创新点、论文大纲、实验分析，或润色论文段落。

## Project Structure

```text
ScholarOS/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── common/
│   ├── modules/
│   │   ├── paper_builder/
│   │   ├── paper_reader/
│   │   ├── code_reader/
│   │   └── paper_writer/
│   └── prompts/
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── markdown.js
│   └── styles.css
├── paper_tools/
├── data/
├── tests/
├── api_server.py
├── paper_finder_agent.py
├── .env.example
└── requirements.txt
```

`api_server.py` 保持兼容，实际 FastAPI app 位于 `backend/main.py`。

## Setup

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填入 OpenAI-compatible LLM 配置，例如 DeepSeek：

```text
DEEPSEEK_API_KEY=sk-...
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

## Run

```powershell
python -m uvicorn api_server:app --host 127.0.0.1 --port 8000 --reload
```

然后打开：

```text
http://127.0.0.1:8000/
```

## API

```text
GET  /api/agents
POST /api/agents/paper-builder
POST /api/agents/paper-reader
POST /api/agents/code-interpreter
POST /api/agents/paper-writer
POST /api/chat
```

会话和论文库接口：

```text
GET    /api/sessions
POST   /api/session
GET    /api/session/{session_id}
PATCH  /api/session/{session_id}
DELETE /api/session/{session_id}
POST   /api/session/{session_id}/papers
```

兼容旧检索入口：

```text
GET /api/search?direction=OE%20Dataset%20Selection&limit=5&sort=relevance&skip_pdf=true
```

## CLI

```powershell
python .\paper_finder_agent.py "OE Dataset Selection" --limit 5 --json --skip-pdf --skip-citations
```

## Data

SQLite 本地数据库位于：

```text
data/scholaros.db
```

GitHub 仓库读取会缓存到：

```text
data/repos/
```
