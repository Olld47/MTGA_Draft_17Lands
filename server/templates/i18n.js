// Lightweight en/zh localization for the static site.
// The preference lives under its own key (mtga-draft-tool-site.lang),
// separate from the desktop app's mtga.lang — localStorage is origin-scoped,
// and the Tauri webview (tauri://localhost) never shares storage with this
// GitHub Pages site, so one key cannot carry a choice across them anyway.
// Load this script BEFORE app.js / calendar.js on every page — they call
// I18N.t() while rendering dynamic content, and both re-render on the
// 'mtga:langchange' event fired when the visitor switches language.
(function () {
  'use strict';

  const STORAGE_KEY = 'mtga-draft-tool-site.lang';

  const MESSAGES = {
    en: {
      // --- Shared (nav / footer) ---
      'nav.app': 'App & Downloads',
      'nav.releases': 'Releases',
      'nav.warehouse': 'Data Warehouse',
      'nav.calendar': 'Schedule',
      'nav.docs': 'API Docs',
      'nav.language': 'Language',
      'footer.about':
        'An open-source desktop overlay. Not affiliated with Wizards of the Coast. This project minimizes API load by aggregating data into single daily files via an automated ETL pipeline.',
      'footer.telemetry': 'Draft telemetry provided by',
      'footer.metadata': 'Card metadata sourced from',
      'footer.projectLinks': 'Project Links',
      'footer.sourceCode': '🔗 Source Code (GitHub)',
      'footer.downloadReleases': '📦 Download Releases',
      'footer.reportIssue': '🐛 Report an Issue / Bug',
      'footer.joinDiscussion': '💬 Join the Discussion',
      'footer.support': 'Support the Creators',
      'footer.supportText':
        'This tool is completely free, but it relies on platforms that pay for expensive servers. If you find this useful, please consider supporting them!',
      'footer.support17lands': '❤️ Support 17Lands on Patreon',
      'footer.supportScryfall': '💜 Support Scryfall on Patreon',

      // --- index.html ---
      'index.title': 'MTGA Draft Tool - 17Lands Overlay',
      'index.hero.draftLike': 'Draft Like a',
      'index.hero.pro': 'Pro.',
      'index.latestRelease': 'Latest Release:',
      'index.windowsDesc': 'Standalone Executable',
      'index.macosDesc': 'Native .app Bundle',
      'index.marqueeFeatures': 'Marquee Features',
      'index.featureBrain': 'Tactical Advisor ("The Brain")',
      'index.featureBrainText':
        'A custom formulaic engine that calculates a 0-100 score for cards in your pack. It dynamically weighs raw Z-Score power, color commitment, curve needs, and relative wheel probability to suggest optimal picks.',
      'index.featureDeck': 'Interactive Deck Builder',
      'index.featureDeckText':
        'Drag-and-drop customization with a 1-click Auto-Lands button. Run a 10,000 game Monte Carlo simulation or use the background AI Optimizer to brute-force the mathematically perfect 40-card configuration.',
      'index.featureDatasets': 'Automated Cloud Datasets',
      'index.featureDatasetsText':
        'Powered by our custom daily ETL pipeline. The app silently downloads pre-compiled 17Lands telemetry in the background so you never have to manually scrape data before a draft again.',
      'index.quickStart': 'Quick Start',
      'index.qs1': 'Download and extract the latest release for your OS.',
      'index.qs2':
        'In MTG Arena, go to <strong>Options -&gt; Account -&gt; Check "Detailed Logs"</strong>.',
      'index.qs3':
        'Launch the app. It will automatically download datasets for currently active events.',
      'index.qs4':
        'Start drafting! The app will automatically read the cards you see in MTG Arena.',
      'index.community': 'Community & Support',
      'index.reportBug': '🐛 Report a Bug',
      'index.reportBugText': 'Create an issue on GitHub',
      'index.discussions': '💬 Discussions',
      'index.discussionsText': 'Ask questions & share ideas',
      'index.requestFeature': '💡 Request a Feature',
      'index.requestFeatureText': 'Help shape the future of the tool',
      'index.faq': 'Frequently Asked Questions',
      'index.faqMacTitle': 'Why does macOS say the app is "damaged"?',
      'index.faqMacText':
        'Because this is a free, open-source project, it isn\'t signed with a paid Apple Developer Certificate. macOS aggressively quarantines unsigned apps. To run it safely, open Terminal and type <code>xattr -cr </code> (include the space), then drag the <strong>MTGA_Draft_Tool.app</strong> into the Terminal window and press Enter.',
      'index.faqUpdateTitle': "The app isn't updating when I pick cards.",
      'index.faqUpdateText':
        'Double check that you have enabled <strong>Detailed Logs (Plugin Support)</strong> inside MTG Arena\'s Account settings. If the app ever severely desyncs, click the <strong>Rescan</strong> button on the dashboard to force it to re-read the log file from the beginning.',
      'index.faqDataTitle':
        'The app says "Unable to access local Arena Data" or datasets fail to download.',
      'index.faqDataText':
        'If MTG Arena is installed in a non-standard location (like a secondary Steam library drive), the application might fail to automatically locate your local card database. To fix this, open the app, go to <strong>Settings -&gt; Locations</strong> and use <strong>Locate... / Browse...</strong> to point the <strong>Arena log</strong> and <strong>MTGA database</strong> fields at your custom <code>Player.log</code> and <code>MTGA_Data</code> folder.',

      // --- releases.html ---
      'releases.title': '🚀 Release History',
      'releases.subtitle':
        'Changelog and previous versions of the MTGA Draft Tool.',
      'releases.loading': 'Loading release history from GitHub...',

      // --- warehouse.html ---
      'warehouse.title': '📦 MTGA Dataset Warehouse',
      'warehouse.lastUpdated': 'Checking last update time...',
      'warehouse.poweredBy': 'Powered by',
      'warehouse.pipelineStatus': 'Pipeline Status',
      'warehouse.duration': 'Duration',
      'warehouse.totalDatasets': 'Total Datasets',
      'warehouse.apiRequests': 'API Requests',
      'warehouse.loading': 'Loading...',
      'warehouse.todayActivity': "Today's Pipeline Activity",
            'warehouse.colSet': 'Set',
      'warehouse.colFormat': 'Format',
      'warehouse.colUserType': 'User Type',
      'warehouse.colDataRange': 'Data Range',
      'warehouse.colGames': 'Games',
      'warehouse.colSize': 'Size (KB)',
      'warehouse.colDownload': 'Download',
      'warehouse.tableLoading': 'Loading data...',
      'warehouse.availableDownloads': 'Available Downloads',
      'warehouse.searchPlaceholder': 'Search sets or formats...',
      'warehouse.manifestLoading': 'Loading manifest...',

      // --- calendar.html ---
      'calendar.title': '📅 MTGA Event Calendar',
      'calendar.subtitle':
        'Visual schedule of when 17Lands datasets are actively aggregated by the ETL pipeline.',
      'calendar.prev': '← Previous',
      'calendar.next': 'Next →',
      'calendar.loading': 'Loading Calendar...',

      // --- docs.html ---
      'docs.title': '📖 Dataset Schema & API',
      'docs.subtitle': 'Interactive documentation for the .json.gz data files.',
      'docs.intro':
        'The ETL pipeline produces a compressed JSON dataset (<code>.json.gz</code>) for each specific MTG Arena event. These files combine MTGA local client IDs, Scryfall metadata, Scryfall community tags (otags), and 17Lands telemetry into a single, unified JSON document optimized for local applications and data analysis.',
      'docs.pathRequired': 'string • required',
      'docs.setParam':
        'The 3-letter MTG expansion code (e.g., <code>BLB</code>, <code>OTJ</code>).',
      'docs.formatParam':
        'Event type (e.g., <code>PremierDraft</code>, <code>TradDraft</code>).',
      'docs.userGroupParam':
        'Player skill bracket (e.g., <code>All</code>, <code>Top</code>).',
      'docs.dataModels': 'Data Models (Schemas)',
      'docs.rootObject': 'Root Object',
      'docs.colProperty': 'Property',
      'docs.colType': 'Type',
      'docs.colDescription': 'Description',
      'docs.metaDesc':
        'Information about when the dataset was compiled.',
      'docs.colorRatingsDesc':
        'Baseline win rates for each color archetype in the format. Keyed by normalized WUBRG strings (e.g., <code>"UB"</code>, <code>"WUBRG"</code>).',
      'docs.cardRatingsDesc':
        'Dictionary of all cards in the set, keyed by the <strong>MTG Arena GrpId</strong> (as a string).',
      'docs.metaVersionDesc': 'Schema version (e.g. <code>3.0</code>)',
      'docs.metaStartDateDesc': 'Start of 17Lands telemetry range.',
      'docs.metaEndDateDesc': 'End of 17Lands telemetry range.',
      'docs.metaGameCountDesc':
        'Total number of games analyzed to build this dataset.',
      'docs.metaCollectionDateDesc':
        'When the ETL pipeline actually compiled the file.',
      'docs.cardNameDesc': 'Sanitized English card name.',
      'docs.cardCmcDesc': 'Converted Mana Cost (Mana Value).',
      'docs.cardManaCostDesc':
        'Formatted mana cost (e.g., <code>"{1}{W}{U}"</code>).',
      'docs.cardTypesDesc':
        'Supertypes (e.g., <code>["Creature", "Artifact"]</code>).',
      'docs.cardSubtypesDesc':
        'Tribes/Types (e.g., <code>["Human", "Ninja"]</code>).',
      'docs.cardRarityDesc':
        '<code>common</code>, <code>uncommon</code>, <code>rare</code>, <code>mythic</code>.',
      'docs.cardColorsDesc': 'Color identity (e.g., <code>["W", "B"]</code>).',
      'docs.cardTagsDesc':
        'Scryfall Oracle tags indicating the card\'s role (e.g., <code>["removal", "evasion", "fixing_ramp"]</code>).',
      'docs.cardImageDesc':
        'List of image URLs (arrays handle double-faced cards).',
      'docs.cardDeckColorsDesc':
        'Contains 17Lands telemetry data isolated by deck archetype (e.g. <code>"All Decks"</code>, <code>"UB"</code>).',
      'docs.metricsGihwrDesc':
        '<strong>Games in Hand Win Rate (%).</strong> The win rate when the card was drawn or in the opening hand. The most standard metric of power.',
      'docs.metricsAlsaDesc':
        '<strong>Average Last Seen At.</strong> (1.0 - 15.0) Indicates how highly the community values picking this card.',
      'docs.metricsAtaDesc':
        '<strong>Average Taken At.</strong> Similar to ALSA, but restricted only to when users of 17Lands actively picked it.',
      'docs.metricsIwdDesc':
        '<strong>Improvement When Drawn (%).</strong> <code>GIHWR - GNSWR</code>. Highly positive IWDs (&gt; 4.0%) strongly indicate "Bomb" level cards.',
      'docs.metricsOhwrDesc':
        '<strong>Opening Hand Win Rate (%).</strong> High values here usually indicate aggressive 1 or 2-drops.',
      'docs.metricsGpwrDesc':
        '<strong>Games Played Win Rate (%).</strong> The win rate of decks that included this card, regardless of if it was ever drawn.',
      'docs.metricsSamplesDesc':
        'Total number of games this card was drawn in this specific archetype. Use this to determine if the win rate is statistically noisy.',

      // --- app.js dynamic strings ---
      'app.checking': 'Checking...',
      'app.viewReleases': 'View Releases',
      'app.releasesRateLimit':
        'Failed to load releases (API Rate Limit exceeded). Please check GitHub directly.',
      'app.latestRelease': 'Latest Release',
      'app.publishedOn': 'Published on {date}',
      'app.viewOnGithub': 'View on GitHub',
      'app.previousReleases': 'Previous Releases',
      'app.releasesFailed':
        'Failed to load releases. Please check GitHub directly.',
      'app.lastEtlRun': 'Last ETL Run:',
      'app.noActiveSets': 'No active sets scheduled for today.',
      'app.activeOnArena': 'Active on Arena',
      'app.historicalArchive': 'Historical Archive',
      'app.noDatasetsFound': 'No datasets found for this view.',
      'app.download': 'Download',
      'app.downloadJson': 'Download .json.gz',
      'app.formatFallback': 'Format',

      // --- calendar.js dynamic strings ---
      'calendar.loadingError': 'Error loading calendar:',
      'calendar.renderError': 'Render Error:',
      'calendar.unknown': 'Unknown',
      'calendar.range': '{start} to {end}',
    },

    zh: {
      // --- Shared (nav / footer) ---
      'nav.app': '应用与下载',
      'nav.releases': '版本发布',
      'nav.warehouse': '数据仓库',
      'nav.calendar': '日程',
      'nav.docs': 'API 文档',
      'nav.language': '语言',
      'footer.about':
        '开源桌面覆盖层工具。与威世智（Wizards of the Coast）无关。本项目通过自动化 ETL 流水线将数据聚合为每日单文件，最大限度减少 API 负载。',
      'footer.telemetry': '轮抓遥测数据由',
      'footer.metadata': '卡牌元数据来自',
      'footer.projectLinks': '项目链接',
      'footer.sourceCode': '🔗 源代码 (GitHub)',
      'footer.downloadReleases': '📦 下载发行版',
      'footer.reportIssue': '🐛 提交问题 / Bug',
      'footer.joinDiscussion': '💬 加入讨论',
      'footer.support': '支持创作者',
      'footer.supportText':
        '这个工具完全免费，但它依赖需要支付昂贵服务器费用的平台。如果你觉得有用，请考虑支持它们！',
      'footer.support17lands': '❤️ 在 Patreon 上支持 17Lands',
      'footer.supportScryfall': '💜 在 Patreon 上支持 Scryfall',

      // --- index.html ---
      'index.title': 'MTGA 轮抓工具 - 17Lands 覆盖层',
      'index.hero.draftLike': '像高手一样',
      'index.hero.pro': '轮抓。',
      'index.latestRelease': '最新版本：',
      'index.windowsDesc': '独立可执行文件',
      'index.macosDesc': '原生 .app 应用包',
      'index.marqueeFeatures': '核心功能',
      'index.featureBrain': '战术顾问（"大脑"）',
      'index.featureBrainText':
        '一个自定义公式引擎，为卡包中的每张牌计算 0-100 的评分。它动态权衡原始 Z 分数强度、颜色投入、曲线需求与相对轮抽概率，给出最优选牌建议。',
      'index.featureDeck': '交互式套牌构筑器',
      'index.featureDeckText':
        '拖放式自定义构筑，一键自动配地。运行 10,000 局蒙特卡洛模拟，或使用后台 AI 优化器暴力求解数学上最优的 40 张套牌配置。',
      'index.featureDatasets': '自动化云端数据集',
      'index.featureDatasetsText':
        '由我们自定义的每日 ETL 流水线驱动。应用在后台静默下载预编译的 17Lands 遥测数据，你再也不必在轮抓前手动抓取数据。',
      'index.quickStart': '快速开始',
      'index.qs1': '下载并解压适合你操作系统的版本。',
      'index.qs2':
        '在 MTG Arena 中，进入 <strong>选项 -&gt; 账户 -&gt; 勾选"详细日志"</strong>。',
      'index.qs3': '启动应用，它会自动下载当前进行中赛事的数据集。',
      'index.qs4': '开始轮抓！应用会自动读取你在 MTG Arena 中看到的卡牌。',
      'index.community': '社区与支持',
      'index.reportBug': '🐛 报告问题',
      'index.reportBugText': '在 GitHub 上创建 issue',
      'index.discussions': '💬 讨论区',
      'index.discussionsText': '提问与分享想法',
      'index.requestFeature': '💡 功能建议',
      'index.requestFeatureText': '帮助塑造工具的未来',
      'index.faq': '常见问题',
      'index.faqMacTitle': '为什么 macOS 提示应用"已损坏"？',
      'index.faqMacText':
        '因为这是一个免费开源项目，没有使用付费的 Apple 开发者证书签名。macOS 会严格隔离未签名应用。要安全运行，请打开终端输入 <code>xattr -cr </code>（注意末尾有空格），然后将 <strong>MTGA_Draft_Tool.app</strong> 拖入终端窗口并回车。',
      'index.faqUpdateTitle': '选牌时应用不更新。',
      'index.faqUpdateText':
        '请确认你已在 MTG Arena 的账户设置中开启 <strong>详细日志（插件支持）</strong>。如果应用出现严重不同步，点击仪表盘上的 <strong>Rescan</strong> 按钮，强制从头重新读取日志文件。',
      'index.faqDataTitle': '应用提示"无法访问本地 Arena 数据"或数据集下载失败。',
      'index.faqDataText':
        '如果 MTG Arena 安装在非标准位置（如辅助 Steam 库盘符），应用可能无法自动定位本地卡牌数据库。解决方法：打开应用，进入 <strong>设置 -&gt; 位置</strong>，使用 <strong>Locate... / Browse...</strong> 将 <strong>Arena 日志</strong>和 <strong>MTGA 数据库</strong>指向你的自定义 <code>Player.log</code> 与 <code>MTGA_Data</code> 文件夹。',

      // --- releases.html ---
      'releases.title': '🚀 版本历史',
      'releases.subtitle': 'MTGA 轮抓工具的更新日志与历史版本。',
      'releases.loading': '正在从 GitHub 加载版本历史...',

      // --- warehouse.html ---
      'warehouse.title': '📦 MTGA 数据集仓库',
      'warehouse.lastUpdated': '正在检查上次更新时间...',
      'warehouse.poweredBy': '数据来源',
      'warehouse.pipelineStatus': '流水线状态',
      'warehouse.duration': '耗时',
      'warehouse.totalDatasets': '数据集总数',
      'warehouse.apiRequests': 'API 请求数',
      'warehouse.loading': '加载中...',
      'warehouse.todayActivity': '今日流水线动态',
      'warehouse.colSet': '系列',
      'warehouse.colFormat': '赛制',
      'warehouse.colUserType': '用户类型',
      'warehouse.colDataRange': '数据区间',
      'warehouse.colGames': '对局数',
      'warehouse.colSize': '大小 (KB)',
      'warehouse.colDownload': '下载',
      'warehouse.tableLoading': '正在加载数据...',
      'warehouse.availableDownloads': '可下载数据集',
      'warehouse.searchPlaceholder': '搜索系列或赛制...',
      'warehouse.manifestLoading': '正在加载清单...',

      // --- calendar.html ---
      'calendar.title': '📅 MTGA 赛事日历',
      'calendar.subtitle':
        '可视化展示 ETL 流水线正在聚合哪些 17Lands 数据集的日程。',
      'calendar.prev': '← 上个月',
      'calendar.next': '下个月 →',
      'calendar.loading': '正在加载日历...',

      // --- docs.html ---
      'docs.title': '📖 数据集结构与 API',
      'docs.subtitle': '.json.gz 数据文件的交互式文档。',
      'docs.intro':
        'ETL 流水线为每个 MTG Arena 赛事生成压缩的 JSON 数据集（<code>.json.gz</code>）。这些文件将 MTGA 本地客户端 ID、Scryfall 元数据、Scryfall 社区标签（otags）和 17Lands 遥测数据合并为一份统一的 JSON 文档，专为本地应用与数据分析优化。',
      'docs.pathRequired': 'string • 必填',
      'docs.setParam': '3 字母 MTG 系列代码（如 <code>BLB</code>、<code>OTJ</code>）。',
      'docs.formatParam': '赛事类型（如 <code>PremierDraft</code>、<code>TradDraft</code>）。',
      'docs.userGroupParam': '玩家技术分组（如 <code>All</code>、<code>Top</code>）。',
      'docs.dataModels': '数据模型（结构）',
      'docs.rootObject': '根对象',
      'docs.colProperty': '字段',
      'docs.colType': '类型',
      'docs.colDescription': '描述',
      'docs.metaDesc': '数据集编译时间相关信息。',
      'docs.colorRatingsDesc':
        '该赛制中各颜色色组的基准胜率。按规范化的 WUBRG 字符串键控（如 <code>"UB"</code>、<code>"WUBRG"</code>）。',
      'docs.cardRatingsDesc':
        '系列中所有卡牌的字典，以 <strong>MTG Arena GrpId</strong>（字符串）为键。',
      'docs.metaVersionDesc': '结构版本号（如 <code>3.0</code>）',
      'docs.metaStartDateDesc': '17Lands 遥测数据范围起点。',
      'docs.metaEndDateDesc': '17Lands 遥测数据范围终点。',
      'docs.metaGameCountDesc': '构建该数据集所分析的对局总数。',
      'docs.metaCollectionDateDesc': 'ETL 流水线实际编译该文件的时间。',
      'docs.cardNameDesc': '清理后的英文卡牌名。',
      'docs.cardCmcDesc': '总法术力费用（法术力值）。',
      'docs.cardManaCostDesc': '格式化法术力费用（如 <code>"{1}{W}{U}"</code>）。',
      'docs.cardTypesDesc': '超类别（如 <code>["Creature", "Artifact"]</code>）。',
      'docs.cardSubtypesDesc': '部族/类别（如 <code>["Human", "Ninja"]</code>）。',
      'docs.cardRarityDesc':
        '<code>common</code>（普通）、<code>uncommon</code>（非普通）、<code>rare</code>（稀有）、<code>mythic</code>（秘稀）。',
      'docs.cardColorsDesc': '颜色身份（如 <code>["W", "B"]</code>）。',
      'docs.cardTagsDesc':
        'Scryfall Oracle 标签，表示卡牌的角色定位（如 <code>["removal", "evasion", "fixing_ramp"]</code>）。',
      'docs.cardImageDesc': '图片 URL 列表（数组形式以支持双面卡）。',
      'docs.cardDeckColorsDesc':
        '包含按套牌色组隔离的 17Lands 遥测数据（如 <code>"All Decks"</code>、<code>"UB"</code>）。',
      'docs.metricsGihwrDesc':
        '<strong>手牌胜率（%）</strong>。卡牌在手牌或起手时抽到的胜率。衡量卡牌强度的最标准指标。',
      'docs.metricsAlsaDesc':
        '<strong>平均最后被选位（ALSA）</strong>。（1.0 - 15.0）表示社区对该卡牌选牌价值的评价。',
      'docs.metricsAtaDesc':
        '<strong>平均被选位（ATA）</strong>。与 ALSA 类似，但仅统计 17Lands 用户实际选择该卡的数据。',
      'docs.metricsIwdDesc':
        '<strong>抽到时的胜率提升（%）</strong>。<code>GIHWR - GNSWR</code>。IWD 显著为正（&gt; 4.0%）强烈表明是"炸弹"级卡牌。',
      'docs.metricsOhwrDesc':
        '<strong>起手胜率（%）</strong>。数值高通常意味着强力的 1 或 2 费快攻曲线。',
      'docs.metricsGpwrDesc':
        '<strong>登场胜率（%）</strong>。包含该卡牌的套牌胜率，无论该卡是否被抽到。',
      'docs.metricsSamplesDesc':
        '该卡在此特定色组中被抽到的对局总数。用它判断胜率是否在统计上有噪音。',

      // --- app.js dynamic strings ---
      'app.checking': '检查中...',
      'app.viewReleases': '查看发行版',
      'app.releasesRateLimit': '加载发行版失败（超出 API 速率限制）。请直接查看 GitHub。',
      'app.latestRelease': '最新版本',
      'app.publishedOn': '发布于 {date}',
      'app.viewOnGithub': '在 GitHub 上查看',
      'app.previousReleases': '历史版本',
      'app.releasesFailed': '加载发行版失败。请直接查看 GitHub。',
      'app.lastEtlRun': '上次 ETL 运行：',
      'app.noActiveSets': '今天没有排期的活跃系列。',
      'app.activeOnArena': 'Arena 现役',
      'app.historicalArchive': '历史存档',
      'app.noDatasetsFound': '此视图下未找到数据集。',
      'app.download': '下载',
      'app.downloadJson': '下载 .json.gz',
      'app.formatFallback': '赛制',

      // --- calendar.js dynamic strings ---
      'calendar.loadingError': '加载日历出错：',
      'calendar.renderError': '渲染出错：',
      'calendar.unknown': '未知',
      'calendar.range': '{start} 至 {end}',
    },
  };

  function currentLang() {
    try {
      const param = new URLSearchParams(window.location.search).get('lang');
      if (param === 'en' || param === 'zh') return param;
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'en' || stored === 'zh') return stored;
    } catch {
      // Storage disabled (private mode) — fall through to browser language.
    }
    const nav = (navigator.language || 'en').toLowerCase();
    return nav.startsWith('zh') ? 'zh' : 'en';
  }

  let lang = currentLang();

  /** Translate a message key; interpolates {name} placeholders via `vars`. */
  function t(key, vars) {
    let s = MESSAGES[lang][key] ?? MESSAGES.en[key] ?? key;
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        s = s.split(`{${k}}`).join(String(v));
      }
    }
    return s;
  }

  /** Apply translations to every annotated static element (idempotent). */
  function applyStatic() {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      el.textContent = t(el.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-html]').forEach((el) => {
      el.innerHTML = t(el.dataset.i18nHtml);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll('[data-i18n-title]').forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
  }

  function setLang(next) {
    if (next !== 'en' && next !== 'zh') next = 'en';
    if (next === lang) {
      applyStatic();
      return;
    }
    lang = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage disabled — the switch still applies for this session.
    }
    applyStatic();
    // Dynamic renderers (warehouse tables, calendar grid, releases list)
    // re-render on this event.
    document.dispatchEvent(
      new CustomEvent('mtga:langchange', { detail: { lang: next } }),
    );
  }

  function init() {
    applyStatic();
    const switcher = document.getElementById('lang-switcher');
    if (switcher) {
      switcher.value = lang;
      switcher.addEventListener('change', () => setLang(switcher.value));
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.I18N = { t, getLang: () => lang, setLang, applyStatic };
})();
