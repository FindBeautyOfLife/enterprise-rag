# Enterprise RAG · 知序知识库工作台

面向中文文档的知识库管理与检索增强问答系统，提供 FastAPI 接口和浏览器工作台，支持多知识库、文档管理、检索测试及可追溯问答。

## 启动

在项目根目录执行，使用 Python 3.10 及以上版本，建议创建独立虚拟环境，再执行：

```powershell
python -m pip install -r requirements.txt
# 仅在没有 .env 时执行；已有配置请保留。
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

打开 <http://127.0.0.1:8000>，接口文档为 <http://127.0.0.1:8000/docs>。前端由同一个服务托管，无需 Node 构建或额外启动前端。

1. 点击左侧 `＋` 创建知识库。
2. 上传 `.docx`、`.txt` 或 `.md`。使用自己有权处理的文档；原始资料不随仓库分发。
3. 通过“预览”检查分块；“检索测试”的关键词模式此时即可使用。
4. 点击“重建索引”，然后使用混合检索或知识问答。

默认 embedding 使用本地 `data/models/bge-small-zh-v1.5`，要求 CLS pooling 和 512 维。Reranker 默认 `BAAI/bge-reranker-base`，首次使用若无缓存需要下载，也可在 `.env` 中设为本地模型路径。问答需要配置 `DASHSCOPE_API_KEY`；文档管理、关键词检索不需要密钥。

## 核心功能

- 知识库创建、编辑、删除，文档数与分块数统计。
- 文档批量选择/拖拽上传、内容去重、原文下载、替换、删除和分块分页预览。
- SQLite 持久化原文件、解析结果及索引版本；每个知识库独立的 Chroma 索引。
- 新索引构建成功后切换；构建失败保留上一个索引版本。
- 关键词检索，以及 Dense + BM25 + RRF + Parent + Rerank 混合检索。
- LangGraph 编排查询改写、证据评估、重试、生成与引用编号校验，支持查看引用原文。
- 中文响应式前端、操作反馈及错误提示。
- 问答消息独立滚动，输入区保持可见；支持清空对话、回到最新消息和 Ctrl / ⌘ + Enter 发送。

## 验证

```powershell
python -m unittest discover -s tests -v
# 使用真实本地模型，独立临时数据，不调用付费大模型 API。
python scripts/31_smoke_knowledge.py
python scripts/31_smoke_knowledge.py --hybrid
```

可选浏览器验收脚本：`tests/browser_smoke.cjs`。需可导入的 Playwright 包和 Microsoft Edge，默认连接 `http://127.0.0.1:8765`。先以临时 `RAG_DATA_DIR` 启动服务，再执行 `node tests/browser_smoke.cjs`。脚本会创建并删除测试知识库，截图写入 `tests/artifacts/`。

问答布局回归：`node tests/chat_layout.cjs`。使用模拟回答，验证多轮长对话、引用展开、滚动位置和多种窗口尺寸，不调用实际大模型接口。

## 运行边界

当前为本地单进程版本，使用默认一个 Uvicorn worker。长时间索引/推理操作由锁串行处理，以保持版本一致。没有登录、权限控制或后台任务队列，请保持绑定 `127.0.0.1`。上传大小默认 20 MB，DOCX 解压文本容器上限 50 MB；暂不支持 PDF、图片 OCR 或 `.doc`。

应用数据默认存于 `data/knowledge/`；独立检索实验使用 `data/chroma_db/`。`/api/v1/ask` 必须提供 `knowledge_base_id`，明确指定问答使用的知识库。

详细开发步骤、表结构、接口、索引一致性和测试说明见 [知识库管理开发详解](docs/知识库管理开发详解.md)。

## 技术栈与项目结构

后端使用 FastAPI / Uvicorn，SQLite 保存原始资料，Chroma 保存向量索引；文档解析使用 python-docx 与 LangChain，检索使用 Sentence Transformers、jieba、BM25 和 RRF，LangGraph 编排问答，OpenAI Python SDK 调用 DashScope 兼容接口。前端为原生 HTML / CSS / JavaScript，无需构建。

```text
src/api/          HTTP 接口与前端托管
src/services/     知识库和问答服务
src/loaders/      文档解析
src/embeddings/   嵌入模型
src/retrievers/   召回、融合、父段检索及重排
src/agent/        LangGraph 工作流
src/generation/   大模型客户端及答案生成
src/vectorstores/ Chroma 与文档标识
frontend/         浏览器界面
scripts/          原实验流程及本地冒烟脚本
tests/            单元测试与可选浏览器测试
docs/             架构、接口与验证说明
data/             本地资料、模型与运行数据（不随仓库分发）
```

## 环境变量

复制 `.env.example` 到项目根目录 `.env` 后填写。进程环境变量优先；相对路径按启动工作目录解析，请从项目根目录启动。

| 变量 | 默认值 / 用途 |
| --- | --- |
| `DASHSCOPE_API_KEY` | 留空；使用问答时填入自己的密钥 |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1`；兼容接口地址 |
| `RAG_LLM_MODEL` | `qwen-plus`；生成模型 |
| `RAG_EMBEDDING_MODEL` | 项目下 `data/models/bge-small-zh-v1.5`；本地模型路径或模型标识 |
| `RAG_RERANKER_MODEL` | `BAAI/bge-reranker-base`；可改成本地模型路径 |
| `RAG_DEVICE` | `cpu` |
| `RAG_MAX_UPLOAD_MB` | `20`；单文件上传上限，单位 MB |
| `RAG_DATA_DIR` | 项目下 `data/knowledge`；本地持久化目录 |

真实密钥仅放在本地环境变量或 `.env`，不要写入代码、文档、测试或截图。

## 首次克隆后的模型与资料准备

仓库排除了 `data/models/`、`data/documents/`、`data/knowledge/` 和 `data/chroma_db/`。本地已有文件会保留；其他开发者克隆后需要自行准备模型和资料，资料数据库由服务初始化创建。文档管理和关键词检索无需模型权重或 API Key。

需要向量检索时，可将 `.env` 中的 `RAG_EMBEDDING_MODEL` 设为 `BAAI/bge-small-zh-v1.5`，由模型库首次加载时下载，或提供本地模型目录。项目现有索引使用 512 维 BGE CLS pooling；请核查模型的 `1_Pooling/config.json`，确保 CLS pooling 开启、mean pooling 关闭，并使用归一化向量。模型或 pooling 变化后应重建索引。重排模型默认 `BAAI/bge-reranker-base`，首次使用可能下载。下载需要联网并遵守模型许可；处理私有资料时可提前准备本地模型。

`scripts/30_pin_embedding_model.py` 依赖旧 `nuist_charter_v1` 集合和参考向量，用于模型与参考向量的一致性校验，不适合作为空仓库首次安装命令。其他编号脚本用于独立检索实验，部分依赖本地章程与旧索引。日常使用优先按本文 API 启动流程操作。

## 公开发布与数据边界

当前服务没有认证或用户权限控制，仅用于可信本机环境，保持监听 `127.0.0.1`，不要直接暴露到公网。问答会将问题和检索到的文档片段发送至所配置的大模型服务，只使用已获授权可发送的资料。流程日志不打印问题正文；第三方异常日志仍可能包含路径和服务详情，分享前须脱敏。

原始 DOCX 可能带有作者、最后修改者等元数据，公开分发前请确认内容权利并检查元数据。默认不提交原始资料、数据库、模型和测试截图。项目尚未附带开源许可证，发布者应确认授权后选择许可证。

可选浏览器测试需要 Node.js、可导入的 Playwright 包及 Microsoft Edge。可先执行 `npm install --no-save playwright`；不要对生产资料运行浏览器验收。
