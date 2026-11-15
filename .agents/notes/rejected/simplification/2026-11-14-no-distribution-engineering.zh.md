# Agent Note: 在分发层之前停下

Status: rejected — 由[Windows agent 交付方案](../../implemented/process/2026-11-14-windows-agent-installation-and-delivery.zh.md)取代。

[English](2026-11-14-no-distribution-engineering.md) | 中文

## 问题

旧设计带着一整套分发层：一个内含 13 MB 引擎归档的 wheel、一个 console script、一个 npm 启动器、一个持有运行期指纹的 `bootstrap` 工具、它旁边的 `doctor` 与 `upgrade` 工具，以及用来证明 wheel 能装上的 CI。这一整套没有读者。这个产品由一个人在一台机器上从检出运行，而分发层在每次依赖变更时都要付费：一次重新构建、两个清单里各改一次版本、一个因为 wheel 移了位置而失败的指纹。

## 提案

安装使用克隆与[开发参考](../../../../docs/development.zh.md)中的锁定依赖命令：一个后端 uv 环境、前端 pnpm workspace，以及包含 MCP 的根 pnpm workspace。工作台控制器负责进程启动；单独的 `python main.py` 只启动引擎，不启动业务 API 或检索进程。仓库不需要我们的包打包配置、安装启动器、运行时指纹、bootstrap 工具或 CI workflow。Windows 启动指南必须针对集成后的控制器验证，才能宣称完成首次调用。

门禁留下：它们是旧机器里真正回本的那部分，几秒钟内本地跑完。分发层不是门禁，而是"为别人打包门禁"。

将来若真需要发行版，最诚实的便宜形态是一个发布归档加一份写明的 sha256，而不是一整套包生态。

## 备选方案

**PyPI wheel 加 `uv tool install`。** 这是旧设计。否决：22 MB 的 wheel 里装着 13 MB 归档、一个运行期 prepare 步骤和一个 console script，全都只是为省掉一次克隆。

**一个 npm 启动器，下载引擎并拉起全部。** 否决：它从 Node 侧安装 Python 工具链，两套生态要同步，而且失败得最难看——启动器成功，运行期不成功。

**一个 `install.ps1` 一次性脚本。** 否决：它是复述 README 的第二条代码路径；脚本比散文腐烂得快，而且那个要判断"这次安装是否可信"的人读不了它。

**容器镜像。** 否决：它并不能省掉引擎自身的安装，Windows 上的 GPU 直通正是最难的部分，而产品本来就假设本机运行。

**每次推送都跑 CI。** 是延后而非否决：门禁本地跑，提交者只有一个人。等到出现第二个贡献者，或出现"未验证不得合并"的分支时，workflow 才值得存在。

## 验收标准

- 在一台只有 git、uv 与 pnpm 的机器上，按 README 步骤能得到可运行的工作台并完成一次真实调用。
- 仓库里没有我们包的打包配置、没有启动器、没有 CI workflow。
- 安装完成后 `git status` 只显示被忽略的产物。

## 风险

- 没有工具链的人无法试用；README 那条路径就是全部的上手成本。
- 将来真做发行版要从零开始，包括那些已经解决过一次的部分。
- Windows 上没有 uv 会多出一步手工操作，README 目前还没覆盖。
