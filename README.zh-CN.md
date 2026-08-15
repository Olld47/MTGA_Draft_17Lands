# MTGA Draft Tool

[English](README.md) · **简体中文**

*本项目是 [unrealities/MTGA_Draft_17Lands](https://github.com/unrealities/MTGA_Draft_17Lands) 的 fork 版本，感谢他的开源。*

一款利用 17Lands 数据的《万智牌：竞技场》(Magic: The Gathering Arena) 轮抓辅助工具。

**每当新系列在 Arena 上线，且该系列的 [17Lands 卡牌评分](https://www.17lands.com/card_ratings) 页面数据可用时，本应用都会自动支持新系列。**

**支持的模式：** 顶级轮抓 (Premier Draft)、传统轮抓 (Traditional Draft)、速配轮抓 (Quick Draft)、现开 (Sealed)、传统现开 (Traditional Sealed) 与 Cube。

## 目录

- [桌面版与旧版界面](#桌面版与旧版界面)
- [安全、校验与 macOS Gatekeeper](#安全校验与-macos-gatekeeper)
- [独立应用运行步骤（Windows / macOS）](#独立应用运行步骤windows--macos)
- [通过 Python 运行（Windows / macOS）](#通过-python-运行windows--macos)
- [亮点功能](#亮点功能)
- [界面导航与标签页](#界面导航与标签页)
- [设置与偏好](#设置与偏好)
- [文件位置](#文件位置)
- [分级表（基于 API）](#分级表基于-api)
- [信号侦测（测试版）](#信号侦测测试版)
- [疑难排查](#疑难排查)
- [开发与文档](#开发与文档)

---

## 桌面版与旧版界面

**PyTauri 桌面应用** —— 在 [Tauri 2](https://tauri.app/) 原生窗口内，以 React + TypeScript 前端运行共享的 Python 轮抓引擎 —— 现已是**默认界面**。旧版 **tkinter 界面**仍然完整支持；当源码目录没有桌面版构建产物时，直接运行源码会回退到 tkinter 界面。

|  | 桌面版（默认） | 旧版 tkinter |
|---|---|---|
| 平台 | macOS（arm64）· Windows（x86_64） | Windows · macOS · Linux |
| 界面 | Tauri 2 内的 React + TypeScript | ttkbootstrap 主题 tkinter |
| 版本序列 | v1.x（`desktop/`） | v4.x（`src/constants.py`） |
| 分发方式 | Releases 页提供 `.dmg` / `.app` · `.msi` / `.exe` | PyInstaller 按需构建 |

入口的分派方式（`main.py`）：

1. 显式的 `--ui desktop` / `--ui tkinter` 参数永远优先。
2. 否则由 `config.json` 中的 `default_ui` 设置决定（默认 `desktop`）。
3. 目标为 `desktop` 时，按顺序查找已构建的二进制：`MTGA_DRAFT_DESKTOP` 环境变量、macOS 下的打包 `.app`、`desktop/target/` 下的 cargo 构建产物；找到即启动。
4. 若不存在构建产物：显式 `--ui desktop` 会打印构建指引并以退出码 2 结束；auto/config 路径则记录警告并**回退到 tkinter**，保证源码目录总能启动某个界面。

如需停留在旧版界面，可将 `config.json` 中的 `default_ui` 设为 `"tkinter"`，或始终传入 `--ui tkinter`。

---

## 安全、校验与 macOS Gatekeeper

由于这是一个免费的开源社区项目，应用未使用付费的 Apple Developer Certificate（每年 $100）签名。因此 macOS 与 Windows SmartScreen 会将该应用标记为「未知开发者」。

为确保下载文件的完整性，我们的 GitHub Actions 流水线会为每个版本自动生成 **SHA-256 校验和**。你可以将下载文件的哈希值与 [Releases 页面](https://github.com/Olld47/MTGA_Draft_17Lands/releases) 上列出的校验值进行比对，以确认文件未被恶意篡改。

**Mac 用户：绕过「应用已损坏」或「恶意软件」提示**
macOS 会主动隔离从网络下载的未签名应用。如需安全运行本应用：

1. 打开**终端**（Command + 空格 -> 「终端」）。
2. 输入 `xattr -cr `（末尾的空格务必保留！）。
3. 将「应用程序」文件夹中的 `mtga-draft-desktop.app` 直接拖入终端窗口。
4. 按**回车**。现在即可正常双击打开应用。

---

## 独立应用运行步骤（Windows / macOS）

- **第 1 步：** 从 [Releases 页面](https://github.com/Olld47/MTGA_Draft_17Lands/releases) 下载适用于你操作系统的最新版本。
- **第 2 步：** 安装/解压应用：
  - **macOS：** 打开 `.dmg` 文件，将 `mtga-draft-desktop.app` 拖入「应用程序」文件夹。*（若 macOS 阻止应用运行，请参见上方「安全」部分。）*
  - **Windows：** 运行 `.msi` 安装程序（或 `.exe`）完成安装。
- **第 3 步：** 在 MTG Arena 中，进入 **选项 -> 账户**，勾选 **详细日志（插件支持）**。
- **第 4 步：** 启动 **MTGA Draft Tool**。
- **第 5 步：** 应用会自动同步当前 Arena 赛事的数据。你也可以打开**数据集**标签页，手动下载历史系列或自定义日期范围的数据。
  - *注：若 MTG Arena 安装在副盘/自定义目录导致数据集下载失败，请打开**设置**标签页 -> **位置**，将应用的日志与数据库指向你的 `Player.log` 和 `MTGA_Data` 文件夹。*
- **第 6 步：** 通过**设置**标签页配置工具。
- **第 7 步：** 在 MTG Arena 中开始轮抓或现开赛事！

---

## 通过 Python 运行（Windows / macOS）

- **第 1 步：** [下载](https://github.com/Olld47/MTGA_Draft_17Lands/archive/refs/heads/main.zip) 并解压仓库。
- **第 2 步：** 下载并安装 **Python 3.12**。
- **第 3 步：** 打开终端输入 `python --version`（或 `python3 --version`）确认你正在使用 Python 3.12。
- **第 4 步：** 输入 `pip install poetry` 安装 Poetry 包管理器。
- **第 5 步：** 在终端中进入解压后的仓库目录，输入 `poetry install` 安装依赖。
- **第 6 步：**
  - *（仅限 Mac）* 进入 `/Applications/Python 3.12/`，双击 `Install Certificates.command` 安装网络证书。
- **第 7 步：** 在 MTG Arena 中，进入 **选项 -> 账户**，勾选 **详细日志（插件支持）**。
- **第 8 步：** 在终端中输入以下命令启动应用：
  ```bash
  poetry run python main.py
  ```
  存在构建产物时默认启动 PyTauri 桌面版；纯源码目录则回退到 tkinter 界面。`--ui desktop` 强制桌面版（需先构建），`--ui tkinter` 强制旧版界面。开发时如需从源码运行桌面版界面，请参见[本地构建](#本地构建)。
- **第 9 步：** 如果应用提示你提供 Arena 玩家日志的位置，请打开**设置**标签页 -> **位置**，选择你的 MTGA `Player.log` 文件。
- **第 10 步：** 应用会在后台自动下载当前活跃系列的 17Lands 数据。
- **第 11 步：** 在 Arena 中开始你的轮抓。

---

## 亮点功能

- **组合引擎 (Compositional Brain v5.5)：** 一个自研战术引擎，为卡包中的每张卡牌计算 0-100 的 `VALUE` 评分。它会动态权衡原始 Z-Score 强度、颜色通道投入程度、曲线需求与相对轮抓概率，给出最优抓牌建议。⭐ 符号代表精英级「炸弹」单卡。
- **AI 蒙特卡洛自动优化：** 点击「自动优化套牌」按钮，后台模拟引擎会基于 10,000 场模拟对局，数学化地测试不同的套牌组合（16 地与 17 地、用高效 2 费替换笨重 5 费……），找到最优的 40 张配置。
- **现开工作室 (Sealed Studio)：** 专为现开组牌设计的全交互拖放工作区。内置 AI 框架生成器，可自动为你的卡池构建前 3 种数学上最优的套牌变体（例如最佳双色、贪心混色、快攻）。
- **自动化云端数据集：** 应用使用自定义云端 ETL 流水线，每天编译并分发最新的 17Lands 遥测数据。打开应用时，它会立即在后台同步当前 Arena 赛事的数据，你无需再手动抓取数据。你可以[在此](https://unrealities.github.io/MTGA_Draft_17Lands/)查看数据集更新日程。
- **零日卡牌识别：** 发售当天，异画卡牌与基本地会通过动态查询你本地的 MTG Arena SQLite 数据库来解析未知 ID，立即显示正确卡名，彻底消除对第三方 API 更新的等待。
- **迷你模式：** 点击 `迷你模式` 按钮隐藏主面板，显示一个紧凑、可拖动、始终置顶的小窗口。非常适合单显示器或需要覆盖在 Arena 客户端之上使用。
- **动态列：** 右键任意表格（卡包、已选卡牌、卡牌对比）的表头即可自定义显示的列。添加或移除特定 17Lands 统计列，并可拖动表头调整顺序。应用会自动记住你的布局。
- **外观主题：** 在**设置**标签页 -> **外观**中，可选择**跟随系统**、**深色**或**浅色**模式（跟随系统会随操作系统自动切换）。
- **双语界面：** 桌面版内置英文与简体中文两种语言——在**设置**标签页中即可切换，无需重启。

---

## 界面导航与标签页

应用由「实时面板」与多个工作区标签页组成：

### 轮抓面板 (Draft Dashboard)
- **顾问推荐：** 解释当前卡包中前 3 张卡牌背后的数学依据。
- **实时卡包：** 显示当前可供选择的卡牌及其战术评分。
- **已见卡牌（轮转追踪）：** 追踪你此前轮抓时放过的卡牌。
- **侧边栏：** 包含可视化的「开阔通道」信号侦测、当前法力曲线以及卡池构成（生物/咒语/地）。

### 应用标签页
- **已选卡牌：** 查看你已抓取的卡牌。**「切换为可视化视图」**按钮可像 MTG Arena 一样将卡牌按法力曲线列堆叠显示。
- **自定义套牌：** 全交互的套牌构建环境，结合自动生成与手动自定义。提供一键 **自动优化** 与 **自动加地** 按钮，以及实时套牌规模校验。
- **推荐套牌：** AI「推荐套牌」引擎为你的卡池流式生成各色组的套牌构筑，附统计与蒙特卡洛模拟结果，并可将最优构筑发送到自定义套牌标签页。
- **现开套牌：** 现开工作室工作区——仅在现开赛事进行时显示。拖放卡池、生成 AI 框架、构建最优变体。
- **卡牌对比：** 搜索并添加多张卡牌，并排直接对比其各项数据。
- **分级：** 从 17Lands API 导入与管理自定义分级表。
- **数据集：** 本地管理、下载与更新 17Lands 卡牌数据。提供详细的下载摘要，包括成功匹配到 17Lands 遥测数据的 MTGA 卡牌数量。可选择**时间段**（全部时间、最新赛事、上周等）以匹配 17Lands；当加载变慢时，可用**清除系列历史**删除旧数据集并重新同步一份干净副本。
- **设置：** 所有应用偏好、数据位置与语言设置（见下文）。

---

## 设置与偏好

打开**设置**标签页。

- **外观：** 在**跟随系统**（随操作系统）、**深色**与**浅色**之间切换整个界面。
- **界面缩放：** 全局调整应用的文字与图片大小（40% 至 250%）。适合小屏笔记本或超大 4k 显示器。
- **语言：** 在**英文**与**简体中文**之间切换——即时生效，无需重启。
- **套牌筛选：** 选择要显示的套牌筛选，或选择**自动**，让应用跟踪你的抓牌并在通道确认后自动切换到你的颜色组合。
- **筛选格式：** 显示颜色组合（如 UB、BG）或公会/部族名称（如 底密尔 Dimir、葛加理 Golgari）。
- **结果格式：** 将胜率字段（GIHWR、OHWR）的结果在**百分比**（55.0%）、**5 分制评分**与**等级**（A+ 至 F）之间切换。
- **按颜色高亮行：** 根据卡牌的颜色身份为表格行着色。
- **始终置顶：** 让应用窗口保持在 MTG Arena 客户端之上。
- **数据：** 开关数据集自动同步、更新通知、轮抓日志记录（将每步轮抓记录到 `./Logs` 文件夹）与缺失数据集通知。
- **位置：** 手动指定 MTGA `Player.log` 与本地 `MTGA_Data` 数据库文件夹（适用于自定义/副盘安装）。
- **恢复默认：** 将所有设置重置为默认值。

---

## 文件位置

应用将设置与数据保存在特定位置，以确保跨版本持久化。

### 配置文件（`config.json`）
应用按以下顺序查找配置文件：
1. **本地文件夹：** 若应用同目录下存在 `config.json`，则使用之（便携模式）。
2. **系统用户文件夹：**
   - **Windows：** `%APPDATA%\MTGA_Draft_Tool\config.json`
   - **Mac：** `~/Library/Application Support/MTGA_Draft_Tool/config.json`

桌面版与旧版应用共用同一用户目录，因此读取相同的数据集与设置。可通过 `MTGA_DRAFT_BASE_DIR` 环境变量覆盖。

### 数据集与日志
- 下载的卡牌数据存放在 `Sets` 文件夹。
- 自定义分级表存放在 `Tier` 文件夹。
- 应用调试日志存放在 `Debug` 文件夹，轮抓日志存放在 `Logs` 文件夹。

---

## 分级表（基于 API）

MTGA_Draft_17Lands 支持直接在应用内下载与使用 17Lands 分级表。

1. 打开应用中的**分级**标签页。
2. 输入 17Lands 分级表 URL 与自定义名称，然后点击下载。
3. 下载完成后，**右键**任意表格（如实时卡包表）的表头，选择`添加列`，即可加入你的新分级表！

---

## 信号侦测（测试版）

该功能通过分析轮抓过程中传给（放过的）你的卡牌，尝试识别「开阔通道」。

- **工作原理：** 工具会扫描你在**第 1 包**与**第 3 包**中看到的每一个卡包。根据每张卡牌的质量（GIHWR）以及你看到它时的先后顺位（对比其平均抓取顺位 ATA），计算一个「信号分数」。
- **图表：** 侧边栏的「开阔通道」条形图汇总这些分数。高分数（20+）通常表明通道非常开阔，即你的邻座玩家没有在抓该颜色。

---

## 疑难排查

### 已知问题
- **重启 Arena 后卡牌缺失：** Arena 每次重启都会生成新的日志。应用无法追踪 Arena 重启之前抓取的卡牌。

### 失步与遗漏的抓牌
应用具备稳健的崩溃恢复与状态持久化能力。若你在轮抓中途关闭应用（或 MTG Arena 崩溃），只需重新打开应用，即可从上次离开的地方精确续抓。

如果日志文件严重失步，点击顶栏的**重新扫描**按钮。应用会清空当前内存，从头快速重读整个日志文件，并干净地重建你的轮抓状态。

### Arena 日志问题
如果应用无法检测到进行中的赛事，请打开**设置**标签页 -> **位置**，确保选择了正确的 `Player.log`。

### 自定义安装目录
如果 MTG Arena 安装在非标准目录（例如副 Steam 库盘），应用可能无法自动定位本地 MTGA 卡牌数据库，导致数据集下载失败。解决方法是打开**设置**标签页 -> **位置**，选择你的自定义 `MTGA_Data` 文件夹。

---

## 开发与文档

对于想要贡献、复刻或理解本应用架构的开发者，请参阅仓库 `/docs` 目录下的 Markdown 规范文档：

- `00-system-overview.md`
- `01-domain-models.md`
- `02-log-parsing-rules.md`
- `03-business-logic.md`
- `04-external-integrations.md`
- `05-server-etl-pipeline.md`

### 环境搭建

**旧版 tkinter 应用：**

1. **安装 Python 3.12**
2. **安装 Poetry：** `pip install poetry`
3. **安装依赖：**
   ```bash
   poetry install
   ```

**桌面版开发**（需要 Rust 工具链、Node.js 20+ 与 [uv](https://docs.astral.sh/uv/)）：

```bash
cd desktop
uv venv --python 3.13 .venv
VIRTUAL_ENV=$PWD/.venv uv pip install -e ./src-tauri
npm install
VIRTUAL_ENV=$PWD/.venv npm run tauri dev
```

### 运行测试

仓库包含两套测试。

Python（根目录——`tests/` 与 `src/` 一一对应），使用 `pytest` 与 `pytest-cov`：

```bash
poetry run pytest tests/
poetry run pytest tests/ --cov=src
```

桌面版前端（Vitest + React Testing Library）：

```bash
cd desktop && npm test
```

### 自动化发布与版本管理

发布通过 GitHub Actions 全自动完成。流水线会在代码**合并到 `master` 或 `main` 分支时自动触发。** 它从 `desktop/src-tauri/tauri.conf.json` 读取桌面版版本号，以 `v<版本>` 打标签，构建**桌面版安装包**（macOS arm64 `.dmg` / `.app`，Windows x86_64 `.msi` / `.exe`），并连同 SHA-256 校验和与 macOS Gatekeeper 提示发布到 [Releases](https://github.com/Olld47/MTGA_Draft_17Lands/releases) 页面。

桌面版使用**独立的版本序列**（v1.x），与旧版应用的 `src/constants.py` 中的 `APPLICATION_VERSION`（v4.x）相互独立。**桌面版版本号提升是一键命令：** `bump_desktop_version.py <版本>` 以 `desktop/src-tauri/tauri.conf.json` 为单一来源，从一个输入改写全部桌面版清单字面量（`desktop/package.json`、`desktop/package-lock.json`、`desktop/pyproject.toml`、`desktop/src-tauri/pyproject.toml`、`desktop/src-tauri/Cargo.toml`、`desktop/Cargo.lock` 与 `mtga_bridge/version.py`）以及 `CHANGELOG.md` 最顶部的 `## [vX.Y]` 标题——切勿手改清单。`bump_version.py` 脚本仅服务于旧版 tkinter 应用。

*（若在未提升版本号的情况下合并代码到 main，流水线只会重建并重新上传已有发布标签上的安装包——适合热修复。）*

### 本地构建

- **桌面版（默认界面）：** 在仓库根目录运行 `./build_desktop.sh`。需要 `uv`、Node.js/npm 与 Rust 工具链，构建产物位于 `desktop/target/bundle-release/bundle/`。支持的目标为 macOS arm64 与 Windows x86_64——其余组合因缺少 `numba` 轮包而不支持，且 **Linux 不是桌面版目标平台**（旧版 tkinter 应用可在 Linux 上运行）。
- **旧版 tkinter 应用：**
  - **macOS/Linux：**
    ```bash
    poetry run pyinstaller main.spec --clean
    ```
  - **Windows：** 使用 `poetry run pyinstaller main.spec --clean` 编译源码，然后用 [Inno Setup](https://jrsoftware.org/isdl.php#stable) 打开 `builder/Installer.iss`，点击 **Build -> Compile**。
