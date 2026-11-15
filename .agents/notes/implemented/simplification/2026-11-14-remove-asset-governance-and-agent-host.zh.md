# Agent Note: 删除引擎的资产数据库、governance 门与 agent host

Status: implemented

[English](2026-11-14-remove-asset-governance-and-agent-host.md) | 中文

## 问题

vendored 引擎带着三个子系统：要么我们已经有，要么永远用不上。`app/assets` 连同 `app/database` 与 `alembic_db` 是图像文件的第二本台账：它给内容做哈希、按定时器扫描目录、并把扫到的结果写回去——这正是我们自己的素材台账禁止的写入路径，因为台账必须承载帧类型、数据集成员位置、校准关联与原件保护。`app/governance` 是面向签名策略文档的第三方 pack 门禁，而那种 pack 格式我们并不存在。`app/agent_host` 挂载 `/api/agent` 与 `/api/workflows`，让托管 agent 直接驱动引擎，而这正是我们的 MCP 工具面通过自家 HTTP API 所承担的职责。

即使关掉它们也并非没有代价：三个子系统在自身目录之外拥有 195 个调用点，把 `--enable-assets` 变成每个读者都要理解的运行模式，而且 seeder 仍可能在我们负责的工作区边界之外改写素材库。只有当它们不存在时，读者才不可能不小心在它们之上继续搭建。

## 决定

删除 `comfy_api_nodes/`（101 文件、63,829 行）、`app/assets/`（37 文件）、`app/database/`（2 文件）、`alembic_db/`（12 文件）、`app/asset_export.py`、`app/governance.py`、`app/agent_host.py`、`comfy_execution/asset_enrichment.py`、`comfy_execution/media_enrichment.py`、`script_examples/`，以及需要多 GB 权重的 `tests/inference` 与 `tests/compare` 测试套件。

随后把耦合摘掉，而不是打桩：`main.py` 去掉数据库启动、启动拒绝消息、每次 prompt 前后的扫描器暂停、agent host 的启停；`server.py` 去掉资产路由注册、导出管理器、上传时的登记与哈希解析；`execution.py` 去掉 `asset_manager` 参数与输出富化；`nodes.py` 去掉 pack 门禁；`comfy/cli_args.py` 去掉五个开关；`comfy_api/feature_flags.py` 固定报告 `"assets": False`。于是 `SERVER_FEATURE_FLAGS` 不再依赖 `main.py` 在启动时改写。

二十二个引用被删模块的引擎测试随之删除，另有 129 个陈旧的 `__pycache__` 目录一并清掉。`tests-unit/app_test` 从参考检出恢复，去掉了资产扫描器与 prompt worker 暂停行为的测试，因此模型、节点、自定义节点管理器的测试仍可运行。引擎 `requirements.txt` 不包含 `alembic`、`SQLAlchemy` 与 `alembic.ini`；共享 `pyproject.toml` 为独立业务 API 声明 SQLAlchemy 和 Alembic，不恢复引擎数据库模块。

## 行为变化

`/upload/image` 与 `/upload/mask` 仍然保存文件，但返回结果中不再有 `asset` 对象；`/view` 对 `blake3:` 名字返回 `404`，因为已没有代码登记内容哈希。读取 `resp["asset"]` 的客户端必须停止这么做。前端一侧的资产侧栏与它引入的 blake3 widget 值成为死代码。

## 备选方案

保留模块并在启动时禁用：读者仍会遇到这些开关，而 seeder 的写入路径只差一次配置失误。只留扫描器、去掉数据库：扫描器存在的目的就是喂数据库，而它的去重正是我们不需要的那部分。采用引擎台账并加以扩展：它没有帧类型、数据集位置、校准，也没有"必须熬过处理过程的原件"这一概念。双写两本台账：一本素材库两个写入者，且 seeder 的结果在我们的快照之后异步到达。只删调用这三个模块的三个钩子：钩子确实容易删，但模块会作为带着活引用的死重留下来。

## 后果

被删掉的代码集中在一个目录：仅 `comfy_api_nodes` 就有 101 个文件、63,829 行。本次没有任何运行时验证：这台机器没有 torch，所以回执是 `python3 -m compileall` 返回零、被删符号的残留引用 grep 为空、以及真实导入 `comfy.cli_args` 与 `comfy_api.feature_flags` 后显示资产标志为 `False` 且无资产、agent、数据库开关。装上依赖后的首次启动是剩余的那一步证明。

两处删除仍未做。模型动物园（`comfy/ldm` 及其周边的模型加载器）有 97,000 行，要等到使用它们的节点类在同一次改动中被切除才走。上传与查看路由暂时保留：它们是浏览器把本地文件拖进图的唯一通道，而这条通道是否保留属于前端清理的范围，不属于本次。
