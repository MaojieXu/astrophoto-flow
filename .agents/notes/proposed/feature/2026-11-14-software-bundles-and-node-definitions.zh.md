# Agent Note: 软件 bundle 是固定的 manifest、适配器和节点集

Status: proposed

[English](2026-11-14-software-bundles-and-node-definitions.md) | 中文

## Problem

旧工作台把天文软件注册为 bundle：包声明自己的可执行文件、适配器、操作、节点定义和本地化，画布可以放置这些节点，而不需要把软件嵌进工作台。新仓库可以把少量 Siril 节点硬编码，但那样每接一个新工具都要改代码，图不会记录结果由哪个软件版本产生，未注册的可执行文件也会变成隐形依赖。

bundle 还必须由 ComfyUI Manager 分支安装，而不是由第二个安装器安装。这让包布局成为契约的一部分：管理器安装一个目录，工作台从该目录读取 manifest。没有固定文件布局的抽象“bundle”无法被任何一方校验、固定或安装。

## Proposal

一个 bundle 就是一个可安装目录。ComfyUI Manager 分支负责安装和移除；工作台负责校验、注册和执行。目录布局固定：

```text
bundle.json
__init__.py
requirements.txt          # optional
adapter/main.py
operations/*.json
nodes/*.json
locales/en.json
locales/zh.json
app/...                   # optional executable payload
```

`__init__.py` 是无操作的 custom-node 标记，让管理器把目录当作普通 custom-node 包。它导出 `NODE_CLASS_MAPPINGS = {}` 和 `WEB_DIRECTORY = None`。工作台从不把它当作 ComfyUI 节点模块导入；它读取 `bundle.json` 及其引用的文件。

### Bundle manifest

`bundle.json` 是数据，不是可执行代码。它沿用 Bundle SDK v2 的字段名，使现有 bundle 不必再学一套词汇：

```json
{
  "schema_version": 1,
  "package_id": "siril",
  "name": "Siril",
  "description": "Siril operations exposed as workbench nodes.",
  "bundle_version": "0.2.0",
  "release_channel": "stable",
  "software_version": "1.4.4",
  "platform": "windows-x86_64",
  "host_api": 2,
  "executable": "app/bin/siril.exe",
  "version_args": ["--version"],
  "version_output": "siril 1.4.4",
  "adapter": "adapter/main.py",
  "operations": ["operations/autostretch.json"],
  "nodes": ["nodes/autostretch.json"],
  "output_nodes": ["0e2f0e3a-6d4d-4f6e-9a4e-0f3a1b2c3d4e"],
  "commands": "commands.txt",
  "assessments": "assessments.md",
  "locales": { "en": "locales/en.json", "zh": "locales/zh.json" }
}
```

- `package_id` 稳定，并匹配 `^[a-z][a-z0-9-]*$`。
- `bundle_version` 是语义版本；开发构建可以用 `X.Y.Z-dev.N`。
- `software_version` 是外部程序的版本，不是 bundle 的版本。
- `platform` 命名可执行文件平台；首个支持值是 `windows-x86_64`。
- `host_api` 是适配器 API 版本。版本 `2` 就是下面的适配器契约。
- 路径相对 bundle 根目录。绝对路径、`..` 和逃出根目录的路径都无效。
- `output_nodes` 列出输出可以登记为科学结果的节点定义 id。每个 id 都必须出现在 `nodes` 中。
- `commands` 和 `assessments` 是可选文档文件；它们永远不授予执行权限。

### 操作描述

每个 `operations/*.json` 描述一个软件操作。操作是适配器执行的单元，也是节点绑定的对象：

```json
{
  "operation": {
    "package_id": "siril",
    "version": "1.4.4",
    "operation_id": "autostretch",
    "name": "Auto stretch",
    "description": "Apply Siril's automatic histogram stretch.",
    "syntax": "autostretch",
    "scriptable": true,
    "cancel_supported": true,
    "calibration_effect": "none",
    "inputs": [
      {
        "name": "image",
        "type": "APF_SCIENCE",
        "formats": ["fits"],
        "cardinality": "one",
        "required": true,
        "supports_hdu": true,
        "supports_slice": false,
        "multiple_connections": false,
        "data_kind": "image",
        "colour_layout": "planar"
      }
    ],
    "outputs": [
      {
        "name": "result",
        "type": "APF_SCIENCE",
        "formats": ["fits"],
        "cardinality": "one",
        "required": true,
        "role": "image",
        "data_kind": "image",
        "colour_layout": "planar"
      }
    ],
    "parameters": [
      {
        "name": "linked",
        "kind": "boolean",
        "default": true,
        "advanced": false
      }
    ],
    "parameter_widgets": {}
  },
  "preview": {
    "kind": "science-image",
    "input": "image",
    "output": "result",
    "max_edge": 1024
  },
  "automatic_result_preview": true
}
```

`operation_id` 在 bundle 内唯一。输入和输出名唯一且不重叠。`preview.input` 必须命名已声明的图像输入；`preview.output` 必须命名已声明的 `APF_SCIENCE` 输出。`parameter_widgets` 可以增加编辑器提示，但不能改变参数类型或边界。

### 节点定义

每个 `nodes/*.json` 描述一个画布节点。节点定义是画布、服务和适配器之间的契约：

```json
{
  "definition_id": "0e2f0e3a-6d4d-4f6e-9a4e-0f3a1b2c3d4e",
  "source": "package",
  "name": "Auto stretch",
  "description": "Apply Siril's automatic histogram stretch.",
  "category": ["Siril", "Image"],
  "inputs": [{ "name": "image", "type": "APF_SCIENCE" }],
  "outputs": [{ "name": "result", "type": "APF_SCIENCE" }],
  "parameters": [
    {
      "name": "linked",
      "kind": "boolean",
      "default": true,
      "advanced": false
    }
  ],
  "execution": {
    "package_id": "siril",
    "operation_id": "autostretch",
    "inputs": { "image": "image" },
    "parameters": {
      "linked": { "kind": "parameter", "name": "linked" }
    },
    "outputs": { "result": "result" }
  },
  "localizations": {
    "zh": {
      "name": "自动拉伸",
      "description": "应用 Siril 的自动直方图拉伸。",
      "parameter_names": { "linked": "联动通道" }
    }
  }
}
```

- `definition_id` 是稳定 UUID。重命名节点不改变它。
- 每个输入、输出和参数名唯一；三组集合互不重叠。
- `execution.inputs` 把每个节点输入映射到操作输入；`execution.outputs` 把每个节点输出映射到操作输出。
- `execution.parameters` 把节点参数映射到操作参数（`kind: "parameter"`）或固定值（`kind: "fixed"`）。固定值按操作参数 schema 校验。
- `localizations` 覆盖 bundle 声明的每个 locale。缺失名称回退到 bundle 默认名称，但已声明的本地化文件不能包含空值。
- 参数可以标记为 `advanced`，但它仍是同一 schema 和同一保存图的一部分。

### 适配器

`adapter/main.py` 导出四个可调用对象：

```python
def build_plan(operation_id, sources, parameters, directory, **options):
    """Return a NamedProcessPlan for one invocation."""

def parse_result(operation_id, directory, plan, log_path):
    """Inspect the invocation directory and report produced outputs."""

def parse_progress(text):
    """Return a BundleProgress for one log line or chunk."""

def parse_failure(log_path):
    """Return a user-readable failure reason."""
```

`build_plan` 返回 `NamedProcessPlan`，包含：

- `schema_version`：`2`；
- `arguments`：参数列表，永远不是 shell 字符串；
- `outputs`：从已声明输出名到 `ProcessOutput` 的映射；
- `temporary_directory`：调用目录内的临时目录；
- `thread_limit` 和 `environment`：可选的进程控制；
- `linear_sample`：可选的线性输入处理声明。

`ProcessOutput` 命名具体 `files` 和 glob `patterns`，每项带格式、可选最小数量、可选 `allow_empty` 和可选帧数。`supporting_patterns` 声明日志或报告等非科学文件。每个路径相对调用目录或 bundle 根目录；适配器不能写到它们之外。

适配器收到解析后的文件路径和临时输出目录。它永远不收到数据库句柄、bearer 令牌或 shell。工作台在启动进程前校验 plan。

### 校验与注册

启动时以及每次管理器操作之后，工作台扫描已安装 bundle 目录并校验：

1. `bundle.json` 可解析，使用受支持的 `schema_version`，并具有唯一 `package_id`。
2. 每个引用的操作、节点、适配器、locale 和文档文件都存在于 bundle 根目录内。
3. 可执行文件存在，能用 `version_args` 运行，并在空白归一化后精确打印 `version_output`。
4. 适配器在隔离命名空间中导入，并暴露四个可调用对象。
5. 每个操作和节点都有唯一 id；每个节点绑定都解析到已声明的操作、输入、输出和参数。
6. 每个本地化覆盖已声明的操作和节点名称；未知键被拒绝。
7. 操作、节点、plan 或输出 pattern 中的每个路径都留在允许的根目录内。

校验失败的 bundle 以 `invalid` 列出，并带失败字段，不能放置或运行。有效 bundle 以 `ready` 列出；工作台记录 `package_id`、`bundle_version`、`software_version`、`host_api`，以及 `bundle.json` 和每个引用描述文件的哈希。管理器可以重装或更新目录；工作台在下一次图运行前重新校验。

### 固定与结果

图节点存储 `package_id`、`bundle_version`、`host_api`、`definition_id` 和描述文件哈希。打开精确组合不可用的图时，节点显示为不可用并拒绝运行；它永远不会替换成最新版本。

调用冻结操作 id、输入素材或数据集、参数值、软件版本、bundle 版本、适配器哈希和 prompt id。适配器只写入调用目录。成功输出通过正常导入登记：它获得新素材 id、哈希，以及指向调用、输入、bundle 版本和参数快照的来源链接。只下载的输出是导出，不是素材。

## Alternatives considered

**在工作台里硬编码 Siril 节点。** 否决：每接一个新工具都要改代码，软件版本会藏进二进制，结果也无法命名产生它的适配器。

**保留旧的抽象 manifest 和自由文件列表。** 否决：管理器无法校验或安装它，两个 bundle 可以用不兼容的字段名描述同一操作。固定布局和 Bundle SDK v2 字段让契约可检查。

**让每个 bundle 定义自己的安装格式。** 否决：管理器需要为每个 bundle 写插件，工作台也无法区分已安装 bundle 和随便一个目录。首版一种布局就够了。

**让工作台安装和更新 bundle。** 否决：它重复 ComfyUI Manager 分支，制造第二份安装状态，并迫使工作台实现 Git、依赖和回滚。安装属于管理器。

**接受来自引擎的任意节点类型。** 否决：图因此可以执行未注册的命令或导入路径。只有校验过的 bundle manifest 或引擎内置目录才能贡献可执行节点类型。

**在容器里运行每个适配器。** 首版否决：它增加运行时依赖和文件系统映射问题，而真实软件已经是原生进程。隔离以后可以加在适配器后面。

## Acceptance criteria

- bundle 目录按固定布局包含 `bundle.json`、适配器、操作描述、节点描述和 locale 文件。
- `bundle.json` 按 Bundle SDK v2 校验，并把每个引用文件解析到 bundle 根目录内。
- 每个节点绑定解析到已声明的操作、输入、输出和参数；每个输出节点都在 `output_nodes` 中声明。
- 可执行文件的 `version_args` 输出匹配 `version_output`；不匹配会把 bundle 标为 invalid。
- 适配器暴露 `build_plan`、`parse_result`、`parse_progress` 和 `parse_failure`。
- 图记录 `package_id`、`bundle_version`、`host_api`、`definition_id` 和描述文件哈希。
- 不可用版本显示为不可用并拒绝运行；它永远不会被悄悄替换。
- 结果通过正常导入登记，并带指向调用、输入、bundle 版本和参数的来源。

## Risks

- bundle 适配器执行第三方软件。校验和管理器确认降低风险，但不会沙箱化它；信任模型必须写明。
- 固定布局可能不适合需要多个可执行文件或非 Python 适配器的软件。首版接受一个可执行文件和一个 Python 适配器；后续版本可以增加适配器种类而不改节点 schema。
- Bundle SDK v2 字段名带有旧假设。复用它们减少迁移工作，但可能保留已无意义的字段；每个字段必须被实现或被拒绝。
- 管理器可能在图运行时安装目录。工作台固定版本并在下一次运行前重新校验；它不能在活跃调用下替换模块。
- 本地化覆盖可能落后于新操作。缺失键必须校验失败，而不是在中文界面里悄悄显示英文。
- 描述文件哈希覆盖文件，不覆盖可执行文件行为。替换了可执行文件但保留相同版本字符串时，仍会被信任，直到管理器或用户重新校验。
