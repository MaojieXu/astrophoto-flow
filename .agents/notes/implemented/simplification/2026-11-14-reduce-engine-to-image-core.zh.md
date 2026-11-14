# Agent Note: 把 vendored 引擎收缩为图像处理核心

Status: implemented

[English](2026-11-14-reduce-engine-to-image-core.md) | 中文

## 问题

vendored 引擎是完整的上游 ComfyUI 产品，而不是图像处理库。它仍然带着扩散 checkpoint、LoRA、VAE、CLIP 与文本编码器、采样器、ControlNet、模型检测与 patch、背景移除、训练与数据集工具、3D/网格/姿态、视频/音频、全局子图库，以及对应的前端模型库与素材界面。这些都不是静止的死代码：每次启动都会导入额外节点白名单并在 `/object_info` 中暴露数百个节点 id；`models/` 目录会被创建并通过 `/models` 提供；前端还带着天文产品不会运行的工作流的标签页、store 与默认图。产品需要的是图像加载、缩放、裁剪、遮罩、合成、预览与保存；其余部分让读者无法分辨引擎的哪一半才是活的。早先的一轮删除停在生成运行时，因为当时保留的 extras 会反向导入它；当这些 extras 自己也被收缩为纯图像节点后，这条停止线就不存在了。

## 决定

只保留图像处理面。`comfy_extras` 保留 28 个白名单模块加 `color_util.py` 与 `compositor_blend.py`：后处理、遮罩、合成、重批、图像、包围盒、形态学、逻辑、分辨率、图像比较、GLSL、文字叠加、颜色、工具箱、替换、数学、数字转换、画笔、合成器、曲线、文本、循环、基础类型、字符串、任意预览、种子、Canny 与 JSON prompt。`nodes.py` 保留 11 个核心图像类：`SaveImage`、`PreviewImage`、`LoadImage`、`LoadImageMask`、`LoadImageOutput`、`ImageScale`、`ImageScaleBy`、`ImageInvert`、`ImageBatch`、`EmptyImage` 与 `ImagePadForOutpaint`。辅助函数 `reshape_latent_to` 移到 `comfy/utils.py`，后处理不再导入已删除的 latent 模块。

删除模型与生成运行时，而不是把它留在可达位置。这包括 69 个模型/视频/音频/3D/训练的 `comfy_extras` 模块、`chainner_models/`、35 个 `comfy` 根模块（`sd.py`、`model_base.py`、`supported_models*.py`、`model_detection.py`、`model_patcher.py`、`samplers.py`、`sample.py`、`controlnet.py`、`clip_vision.py`、`lora.py`、`hooks.py` 及其支撑环）和 12 个目录（`comfy/ldm`、`text_encoders`、`cldm`、`t2i_adapter`、`taesd`、`k_diffusion`、`extra_samplers`、`image_encoders`、`audio_encoders`、`background_removal`、`weight_adapter`、`sd1_tokenizer`）。AI 放大一并删除：`UpscaleModelLoader` 与 `ImageUpscaleWithModel` 需要 `CoreModelPatcher`，而它又需要 `lora.py`、`model_base.py` 和 patcher 栈；天文路径保留原生 `ImageScale`/`ImageScaleBy`。背景移除也删除：它需要 `comfy/ldm/modules` 与 CLIP 模型，两者都不再保留。

把 API 层裁剪到图像面。`comfy_api` 不再导入或暴露视频、音频、3D 输入辅助类型；`Input` 只保留 `Image` 与 `Mask`；`LoadImage` 去掉 `VideoFromFile` 路径。`comfy_execution/caching.py` 不再导入 model-patcher 输出检测，`main.py` 不再为动态 VRAM 导入 `model_patcher`。

删除模型管理的 HTTP 面：`/embeddings`、`/models`、`/models/{folder}`、`/view_metadata/{folder_name}`、`/experiment/models*`、`/global_subgraphs` 与 `/global_subgraphs/{id}`。删除 `app/model_manager.py` 与 `app/subgraph_manager.py`；`folder_paths` 只认识 `custom_nodes`，`main.py` 不再创建模型目录。全局蓝图库属于这次删除；用户自建子图、litegraph 子图编辑以及 `userdata/subgraphs/` 的保存/加载路径保留。保留 `/features`（远程配置读取它）、`/api/jobs`（队列历史读取它）、`/extensions`（自定义节点 web 目录）与 `/upload/mask`（外部遮罩编辑客户端）。保留 `/upload/image`、`/view`、`/object_info`、`/prompt`、`/history`、`/queue`、`/interrupt`、`/system_stats` 与 `/ws`；它们才是执行与图像 API。

删除对应的前端表面：模型库与素材侧栏标签、`modelStore`、从素材拖出模型节点的辅助函数、扩散默认图、A1111 PNG 导入，以及全局子图加载。新的默认图只有一个 `EmptyImage`；工作流 schema 仍要求至少一个节点，但新建工作流不再铺开 checkpoint/CLIP/VAE/KSampler 链。源码树现在就是被提供的前端：`pnpm build` 产出 `dist/`，启动器用 `--front-end-root ../frontend/dist`，避免改动被 pip 包的静态树掩盖。引擎在 `pyproject.toml` 声明剩余运行时并用 `uv.lock` 锁定，因此干净的 `uv sync --frozen` 能产出可用的 CPU 环境；`uv sync` 不会安装前端构建，所以启动路径必须传 `--front-end-root`。

删除只服务已删栈的依赖：`torchvision`、`transformers`、`tokenizers`、`sentencepiece`、`spandrel`、`torchsde`、`filelock` 与 `blake3`。保留 `av`（`comfy_extras/nodes_images.py` 用它输出 AVIF，`comfy/utils.py` 的共享解码器用它处理 EXR 输入与 `/view` 预览）以及其余小型图像/运行时依赖（`einops`、`safetensors`、`kornia`、`PyOpenGL`、`comfy-angle`、`pydantic`、`packaging`）。

`torch` 保留。所有存活的图像节点都消费和产出 `torch.Tensor`（28 个模块导入它）；它是张量运行时，不是训练依赖，因此只装 CPU wheel 即可，不安装 CUDA 或训练栈。本仓库只 vendored 引擎；外围产品仓库才持有资产服务、CLI、MCP 与启动器，并用自己的环境。早先交接里的 Windows lock 与双环境启动器属于那个产品树，不是对本仓库运行时的陈述。

## 行为变化

`/object_info` 现在返回 116 个类，全部是图像/工具节点；不再有 checkpoint、LoRA、VAE、CLIP、采样器、ControlNet 或放大模型类。`/models`、`/embeddings`、`/view_metadata`、`/experiment/models*` 与 `/global_subgraphs` 返回 404。`models/` 下的模型目录不再注册或创建。新建工作流打开的是 `EmptyImage`，不再是扩散默认图；前端不再显示模型库与素材标签。

## 备选方案

**保留模型运行时，只删节点注册。** 模型类、patcher、LoRA 与 hooks 会通过导入继续可达，并在今后每次改动中增加分支，而天文节点却用不到它们。只删注册不删实现，是让下一位读者继续猜测哪一半才是活的半吊子做法。

**保留 AI 放大的兼容层。** `UpscaleModelLoader` 把 spandrel descriptor 包进 `CoreModelPatcher`，只是为了复用 ComfyUI 的设备/卸载调度。保留它意味着保留 `model_patcher.py`、`hooks.py`、`lora.py`、`model_base.py` 和大约 6,500 行支撑环，而 `model_patcher` 又会拉进 `lora` 与模型类。原生 `ImageScale` 已覆盖天文缩放路径；以后可以不经 patcher 栈直接调用 spandrel，但那是新功能，不是保留扩散运行时的理由。

**保留背景移除。** 它需要 `comfy/ldm/modules` 与 CLIP 编码器，无法与删除模型运行时共存；它也不在天文图像路径上。

**只删后端路由，保留前端模型库。** 运行时提供的是构建产物而非源码；不删调用方、不重建就删路由，会让模型库的每个操作在运行时失败。两边一起删才是加载时就诚实的状态。

## 后果

后端现在是 201 个 Python 文件、43,589 行，从 581 个文件、175,906 行降下来：删除了 380 个文件、132,317 行。`comfy/` 根目录有 12 个模块，`comfy_extras` 有 30 个文件（28 个白名单加两个辅助文件），`/object_info` 有 116 个类。`pytest tests-unit` 通过 885 个测试。服务器从仓库 `.venv` 启动并加载前端 `dist/`，成功执行了真实的 `LoadImage → ImageScale(128×128) → PreviewImage` 工作流，输出为 128×128 PNG。仅用 `uv sync --frozen` 与同一个 `--front-end-root` 的干净临时副本也能启动、提供本地页面、暴露 116 个类并完成该工作流。EXR 输入与 `/view` 预览通过共享 PyAV 解码器处理；默认 EXR 预览请求 WebP，下载仍取原文件；关闭资产库后，作业完成时输出历史仍会刷新。模板入口已隐藏，因为内置模板都不能被图像核心执行。

早先“保留上游路由”的提醒已经消失：`/global_subgraphs` 与模型路由现在是删除，而不是留给仍在调用它们的前端。被删除的只是全局蓝图库；用户子图仍从 `userdata/subgraphs/` 加载，并可编辑和保存。`openapi.yaml` 没有重新生成，仍包含一些已删除的模型/子图端点描述；它是文档，不是路由表。前端完整项目运行有 1 个对时序敏感的 `cameraFraming` 失败，单独运行可通过；fork 工具/CI 脚本仍有 32 个失败，因为它们读取被排除的 `.github/` 树。更新后的 subgraph、sidebar、graph-view 与模块边界测试均通过。

`manager_requirements.txt` 与可选的 `--enable-manager` 路径保留：它们是独立的自定义节点管理器，不属于模型运行时。留下的图像/工具节点是天文专用处理的扩展点；新增图像节点不再有重新注册扩散栈的风险。
