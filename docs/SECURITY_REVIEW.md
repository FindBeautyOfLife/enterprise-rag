# GitHub 公开发布前安全审查

审查日期：2026-11-12。范围：当前工作区文件。所有扫描均在本地执行，没有调用外部扫描服务或真实大模型 API，没有上传文件、推送代码、修改远程配置或改写历史。

## 审查结论

已完成最小范围的配置、文档和日志清理，保留全部业务代码、模型、数据库、原始文档和本地凭证。候选公开文件不含本次识别的本地 API Key 或个人 Windows 用户目录路径。不能据此保证不存在所有未知格式凭证或软件漏洞。

初次检查时，当前目录不是 Git 仓库，递归检查也未发现子仓库。因此不存在可供检查的项目暂存区或本地提交历史；无法证明项目在其他位置或远程从未提交过凭证。此次没有初始化项目仓库。

## 发现的问题与处理

| 位置 | 风险 | 发现 | 处理 / 后续行动 |
| --- | --- | --- | --- |
| `.env:1` | 高（若误上传） | `DASHSCOPE_API_KEY=sk-***`，非空、非明显占位值；未联网验证有效性 | 原值留在本地，不改写、撤销或生成密钥；忽略规则已验证。精确值扫描仅在该文件命中 |
| `.env:2-3` | 低 | 旧变量 `BAILIAN_BASE_URL`、`BAILIAN_MODEL` 不被当前客户端读取；模型选项可能未生效 | 不擅自改动本地配置；README 和模板说明当前变量名，需用户按意图迁移 |
| `构建流程与复盘.md:584` | 中 | 模型位置包含个人 Windows 用户目录和桌面路径 | 替换为 `data/models/bge-small-zh-v1.5` |
| `data/documents/南京信息工程大学章程.docx` 内 `docProps/core.xml` | 中 | 作者和最后修改者字段非空且不是常见默认值；无法确认是否为用户本人信息 | 不修改原始业务文件；整个原始文档目录排除提交。公开分发前人工检查元数据与再分发权限 |
| `src/agent/workflow.py` 的 `rewrite_node`、`retry_node`、`evaluate_node` | 中 | 默认日志输出用户问题、改写问题和原始第三方异常详情 | 改为不含问题正文的流程状态提示，保留算法、异常回退和返回值 |
| `src/generation/llm_client.py` | 低 | 无参 `load_dotenv()` 可能向上搜索 `.env` | 固定加载项目根目录 `.env`，保持环境变量优先和原有参数默认值 |
| `.gitignore` | 中 | 只覆盖准确 `.env` 名称，缺少变体、凭证文件、IDE、日志等规则 | 补充规则，保留 `.env.example`；验证源码、模板不被误排除 |
| `data/knowledge/`、`data/chroma_db/` | 中（若误上传） | 含持久化原文、分块、向量和历史队列，不能当作无敏感信息的缓存 | 继续排除提交，不删除或改写数据库 |
| `data/models/` | 低 | 本地权重约 91.4 MiB，且新克隆项目不会自动获得已排除的本地模型 | 保留排除规则；README 说明模型准备、CLS pooling、512 维和重建索引要求 |
| `README.md`、`.env.example` | 低 | 原安装流程依赖本机特定 Conda 环境，缺少完整配置及新克隆资料准备说明 | 使用独立虚拟环境步骤，列出实际配置项、技术栈、目录及运行边界 |
| `src/api/main.py` | 高（若直接公网部署） | 没有认证与用户授权，接口可读写知识库和下载原文 | 保留本地应用行为，明确仅监听 `127.0.0.1`；没有擅自加入改变使用方式的认证系统 |

正常业务数据与误报：本机回环地址、DashScope 公共兼容接口地址、公开模型标识不是秘密；测试中的 `test-placeholder` 是模拟值。模型上游 README 的公开作者姓名、邮箱和引用资料保留，不作为用户个人凭证删除。没有发现需从业务源码中抽取的硬编码数据库密码、JWT 密钥或云服务认证值。没有发现 Notebook 文件。

## 实际修改文件

1. `.gitignore`：补充环境文件变体、常见私钥容器、凭证文件、虚拟环境、IDE、缓存、日志、可选 Node 依赖、临时审查目录等；新增排除 `data/documents/`，保留全部本地文件。没有忽略所有 JSON/YAML 配置。
2. `.env.example`：空密钥、安全公共接口、完整已使用配置名、相对模型路径及旧变量名提示。
3. `README.md`：完善安装、技术栈、目录、变量表、模型与资料准备、测试方式及发布注意事项，保留实际已有功能和命令。
4. `src/generation/llm_client.py`：限定 dotenv 的加载路径。
5. `src/agent/workflow.py`：日志不再输出问题及改写正文、评估异常详情。
6. `构建流程与复盘.md`：移除个人绝对路径。
7. `requirements.txt`：只调整说明注释，所有依赖名称和版本保持不变，没有导出 Conda 环境。
8. `docs/SECURITY_REVIEW.md`：新增本报告。

没有删除文件、修改真实 `.env`、执行 `git rm` 或批量去除业务数据。`.audit-tmp/` 保存本次可忽略的本地校验产物及临时索引；无需提交。

## 扫描范围与验证

- 递归枚举项目，包括隐藏配置；扫描代码、脚本、测试、文档、配置、模型词表和 tokenizer，以及二进制文件中的已知密钥精确字节和典型凭证形态。报告只记文件与风险，不包含完整凭证。
- 只读打开 3 个 SQLite 数据库，检查表字段内容；未发现本次密钥、个人用户目录或所检查的凭证模式。知识库库有 1 个知识库和 1 份文档，两个 Chroma 数据库分别含 144 与 81 条 embedding。数据库仍排除提交，不因扫描无命中而判定可公开。
- 检查 DOCX 解压后的 XML 与核心元数据；检查 safetensors 文件头及文本元数据。模型张量和向量数值的语义无法通过字符串扫描证明无隐私。
- 目视检查 4 张现有浏览器截图，显示测试资料与模拟回答，未见明显密钥或个人路径；仍排除提交。
- 使用项目内临时 bare Git 元数据与实际工作树，通过 Git 自身的 `check-ignore --no-index -z --stdin` 验证规则；没有创建根目录 `.git`。核验 `.env`、`.env.local`、`.env.production`、私钥、原始资料、模型、数据库和截图被忽略，`.env.example` 与 `src/config.py` 可提交。此验证不等于项目真实暂存区检查。
- 最终共核对 102 个现有文件（不计审查临时目录和 Python 缓存），37 个被忽略、65 个为候选提交文件。候选文件复扫没有发现本次识别的本地密钥或个人用户目录路径，真实密钥精确值仅在被忽略的 `.env` 中命中。模板密钥为空，示例值均为安全默认值；README 本地链接及候选 Python 文件语法复核通过。
- Python 的 53 个源文件语法解析通过；`frontend/app.js`、两个 `.cjs` 浏览器脚本通过 `node --check`。
- 默认 Python 3.13 环境缺少 `python-docx`，首次测试导入失败；随后使用已有 `deep` 环境的 Python 3.10.18 执行现有 8 项单元测试，全部通过。覆盖知识库 CRUD、持久化、隔离、上传校验、文件名清理、DOCX 表格、索引失败恢复与模拟问答。
- `python scripts/31_smoke_knowledge.py` 通过：使用真实本地 BGE/Chroma，验证索引、检索、重连持久化与删除。临时数据位于项目内 `.audit-tmp/`，没有修改原资料或旧索引。
- 测试禁用 `.env` 加载、清空真实 API Key，并设置模型离线模式及关闭 Chroma 遥测。没有执行真实大模型问答或在线依赖漏洞扫描。

- `python scripts/31_smoke_knowledge.py --hybrid` 通过：真实 Dense + BM25 + RRF + Parent + CrossEncoder 全流程离线验证成功。
- 修改完成后再次执行 8 项单元测试，全部通过；输出确认查询改写日志不再包含问题正文。测试中模拟索引失败的异常栈是预期输出。
- `.env.example` 经 `dotenv_values` 解析和 `Settings.from_env()` 核验通过，密钥为空、相对数据目录与 20 MB 上限符合当前代码。
- `deep` 环境中 `python -m pip check` **未通过**：额外安装的 `langchain==1.1.0` 要求 `langgraph>=1.0.2,<1.1.0`，而环境及项目使用 `langgraph==1.2.20`。本项目 requirements 没有声明顶层 `langchain`，现有代码导入的是 `langchain-core`、`langchain-text-splitters` 和 `langgraph`。没有为修复共享环境而擅自降级项目依赖或卸载包；建议在独立环境安装后再检查。现有单元测试及真实检索验证均通过，不能据此忽略该环境冲突。
- jieba 发出 `pkg_resources` 弃用警告，当前测试未因此失败；没有擅自升级依赖。
- 未重跑浏览器交互测试；本次未改前端，完成其 JavaScript 语法检查及现有截图审阅。未进行真实大模型联网启动验证。

## 剩余风险与手动事项

1. **密钥**：没有确认已公开泄露。如果该密钥曾提交、推送、粘贴到公共位置或被他人取得，应先在服务商控制台手动轮换；本次没有擅自验证、撤销、替换或生成真实密钥。
2. **历史**：如另有已有仓库，应在该仓库对全部分支、标签及历史进行离线凭证扫描。若发现泄露，先轮换，再经确认使用 `git filter-repo` 等工具清理历史，协调协作者重新克隆；公开分叉、缓存、克隆和旧归档不一定能清除。不要只依赖 `.gitignore`。
3. **原始资料**：DOCX 作者元数据和内容再分发权需人工确认。未来增加的资料、日志、导出、Notebook 输出与截图需要重新审查，尤其是放到默认数据目录之外的文件。
4. **日志与外发**：业务异常栈和第三方库仍可能打印本地路径或服务响应；不要公开原始日志。正常问答会向配置的模型服务发送问题与检索片段，本次审查没有触发该调用。
5. **依赖**：保留固定版本，部分直接使用的库由上层依赖间接安装（如 Pydantic、Starlette、typing-extensions）。未在新建空环境完整重装，未在线查询 CVE，不能承诺供应链安全。
6. **部署与许可**：公开代码不代表可以直接公网部署。认证、授权、速率限制和资源隔离需要另行设计；本次没有改变核心逻辑。项目未附带 LICENSE，发布者需决定许可，并确认第三方资料、模型及代码授权。

## 建议的提交与推送步骤（仅供用户确认后执行）

当前并非 Git 仓库，以下步骤均尚未执行。先确认报告与待公开内容，再在项目根目录操作：

```powershell
git init
git branch -M main
git check-ignore .env data/documents/ data/models/ data/knowledge/ data/chroma_db/
git status --short --untracked-files=all
git add .gitignore .env.example README.md requirements.txt src frontend scripts tests docs '构建流程与复盘.md'
git diff --cached --check
git diff --cached --name-status
git ls-files -- .env '.env.*' data/ .vscode/ tests/artifacts/
```

最后一条命令应该只出现允许公开的 `.env.example`（当前 `data/` 文件不应出现）。如发现真实凭证或本地资料，先停止提交并用 `git restore --staged -- <文件>` 取消暂存，保留磁盘文件。新仓库第一次提交前若没有 HEAD，可用 `git rm --cached -- <文件>` 只撤销暂存；不要省略 `--cached`，不要使用 `-f` 强制提交忽略文件。

审阅暂存区时只在本地查看，不要把可能含秘密的完整 diff 发到公共服务。确认无误后：

```powershell
git commit -m "Prepare project for public release"
```

然后在 GitHub 创建空仓库，不上传 `.env`、原始资料或模型。核对仓库可见性与地址后，由用户手动设置远程并推送：

```powershell
# 将尖括号内容替换为自己确认过的地址；地址中不要嵌入 Token。
git remote add origin <已确认的仓库地址>
git remote -v
git push -u origin main
```

此处没有执行任何提交、仓库创建、远程修改或推送；最终发布等待用户确认。
