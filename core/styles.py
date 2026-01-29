from __future__ import annotations

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap');

/* ========== Apple 深色简约高级风格 ========== */

/* CSS 变量 - 设计令牌 */
:root {
    /* 背景 */
    --bg-page: #0B0B0E;
    --bg-surface: #16161A;
    --bg-elevated: #1A1A1E;
    
    /* 主色 */
    --accent-primary: #32D583;
    --accent-secondary: #6366F1;
    --accent-coral: #E85A4F;
    
    /* 中性色 */
    --text-primary: #FAFAF9;
    --text-secondary: #6B6B70;
    --text-muted: #4A4A50;
    --border-color: #2A2A2E;
    --border-subtle: #3A3A40;
    
    /* 语义色 */
    --green-success: #32D583;
    --yellow-warning: #FFB547;
    --red-error: #E85A4F;
    --blue-info: #60A5FA;
    
    /* 字体 */
    --font-heading: 'DM Sans', -apple-system, sans-serif;
    --font-body: 'DM Sans', -apple-system, sans-serif;
    
    /* 间距 */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 12px;
    --space-lg: 16px;
    --space-xl: 24px;
    --space-2xl: 32px;
    --space-3xl: 48px;
    
    /* 圆角 */
    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
}

/* 全局字体和背景 */
html, body, [class*="css"] {
    font-family: var(--font-body) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    color: var(--text-primary);
    background: var(--bg-page);
}

.stApp {
    background: var(--bg-page);
}

/* 确保所有文本使用正确颜色 */
.stApp, .stApp p, .stApp span, .stApp div, .stApp label {
    color: var(--text-primary);
}

.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {
    color: var(--text-primary) !important;
}

/* Markdown 文本颜色 */
.stMarkdown, .stMarkdown p, [data-testid="stMarkdownContainer"] p {
    color: var(--text-primary) !important;
}

/* 隐藏 Streamlit 默认元素（保留侧边栏展开按钮） */
#MainMenu, footer {visibility: hidden;}
.stDeployButton {display: none;}
[data-testid="stSidebarNav"] {display: none !important;}

/* 侧边栏展开按钮（汉堡菜单）- 确保在手机上可见且易点 */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    visibility: visible !important;
    display: flex !important;
    position: fixed !important;
    top: 0.75rem !important;
    left: 0.75rem !important;
    z-index: 999999 !important;
    background: var(--bg-surface) !important;
    border-radius: var(--radius-md) !important;
    padding: 0.5rem !important;
}

[data-testid="stSidebarCollapsedControl"] button,
[data-testid="collapsedControl"] button {
    min-width: 44px !important;
    min-height: 44px !important;
    padding: 0.5rem !important;
}

[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="collapsedControl"] svg {
    width: 24px !important;
    height: 24px !important;
    color: var(--text-primary) !important;
}

/* 主内容区 */
.main .block-container {
    padding: var(--space-3xl) var(--space-3xl);
    max-width: 1000px;
    background: var(--bg-page);
}

/* ========== 侧边栏 - Apple 深色风格 ========== */
[data-testid="stSidebar"] {
    background: var(--bg-surface) !important;
    border-right: 1px solid var(--border-color) !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: var(--space-xl) var(--space-lg);
    background: var(--bg-surface) !important;
}

/* 侧边栏标题 */
.sidebar-title {
    font-family: var(--font-heading);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-xl);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    letter-spacing: -0.02em;
    padding: var(--space-md);
    background: linear-gradient(135deg, var(--accent-primary) 0%, #059669 100%);
    border-radius: var(--radius-md);
}

/* 侧边栏导航 */
[data-testid="stSidebar"] .stPageLink a,
[data-testid="stSidebar"] .stPageLink span,
[data-testid="stSidebar"] .stPageLink p,
[data-testid="stSidebar"] a {
    font-family: var(--font-heading) !important;
    color: var(--text-secondary) !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    text-decoration: none !important;
}

[data-testid="stSidebar"] .stPageLink > a,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
    color: var(--text-secondary) !important;
    font-size: 0.875rem !important;
    padding: var(--space-md) var(--space-lg) !important;
    border-radius: var(--radius-md) !important;
    margin-bottom: var(--space-xs) !important;
    display: flex !important;
    align-items: center !important;
    gap: var(--space-md) !important;
    transition: all 0.2s ease !important;
    border-left: none !important;
}

[data-testid="stSidebar"] .stPageLink > a:hover,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
}

/* 当前活动页面高亮 */
[data-testid="stSidebar"] .stPageLink > a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {
    background: var(--accent-primary) !important;
    color: white !important;
}

/* ========== 页面标题 ========== */
.page-title {
    font-family: var(--font-heading);
    font-size: 1.5rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-sm);
    letter-spacing: -0.02em;
}

.page-desc {
    font-family: var(--font-body);
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: var(--space-xl);
    font-weight: 400;
}

/* ========== 统计卡片 - Apple 深色风格 ========== */
.stat-card {
    background: var(--bg-surface);
    border-radius: var(--radius-lg);
    padding: var(--space-lg) var(--space-xl);
    border: 1px solid var(--border-color);
    transition: all 0.2s ease;
}

.stat-card:hover {
    border-color: var(--accent-primary);
    background: var(--bg-elevated);
}

.stat-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: var(--space-md);
    font-weight: 500;
}

.stat-icon {
    width: 20px;
    height: 20px;
}

.stat-value {
    font-family: var(--font-heading);
    font-size: 1.75rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}

.stat-sub {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: var(--space-sm);
    font-weight: 400;
}

/* ========== 按钮样式 - Apple 深色风格 ========== */
.action-btn-primary {
    background: var(--accent-primary);
    color: white;
    border: none;
    border-radius: var(--radius-md);
    padding: 0.875rem 1.5rem;
    font-family: var(--font-heading);
    font-size: 0.875rem;
    font-weight: 600;
    width: 100%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-md);
    transition: all 0.2s ease;
}

.action-btn-primary:hover {
    background: #28b870;
    transform: translateY(-1px);
}

.action-btn-secondary {
    background: var(--bg-surface);
    color: var(--text-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0.875rem 1.5rem;
    font-family: var(--font-heading);
    font-size: 0.875rem;
    font-weight: 500;
    width: 100%;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-sm);
    margin-bottom: var(--space-md);
    transition: all 0.2s ease;
}

.action-btn-secondary:hover {
    border-color: var(--accent-primary);
    background: var(--bg-elevated);
}

/* ========== Streamlit 按钮覆盖 ========== */
.stButton > button {
    font-family: var(--font-heading) !important;
    border-radius: var(--radius-md) !important;
    font-weight: 600 !important;
    font-size: 0.875rem !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.01em !important;
}

.stButton > button[kind="primary"] {
    background: var(--accent-primary) !important;
    border: none !important;
    color: white !important;
}

.stButton > button[kind="primary"]:hover {
    background: #28b870 !important;
    transform: translateY(-1px);
}

.stButton > button[kind="secondary"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-color) !important;
    color: var(--text-primary) !important;
}

.stButton > button[kind="secondary"]:hover {
    border-color: var(--accent-primary) !important;
    background: var(--bg-elevated) !important;
}

/* ========== 报告列表项 - Apple 深色风格 ========== */
.report-item {
    background: var(--bg-surface);
    border-radius: var(--radius-md);
    padding: var(--space-md) var(--space-lg);
    border: 1px solid var(--border-color);
    margin-bottom: var(--space-sm);
    display: flex;
    align-items: center;
    gap: var(--space-md);
    transition: all 0.2s ease;
}

.report-item:hover {
    background: var(--bg-elevated);
    border-color: var(--accent-primary);
}

.report-icon {
    width: 40px;
    height: 40px;
    background: linear-gradient(135deg, var(--accent-primary) 0%, #059669 100%);
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1rem;
    flex-shrink: 0;
}

.report-info {
    flex: 1;
    min-width: 0;
}

.report-title {
    font-family: var(--font-heading);
    font-size: 0.875rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-xs);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.report-meta {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: var(--space-sm);
}

.report-arrow {
    color: var(--text-secondary);
    font-size: 1.25rem;
    transition: all 0.2s ease;
}

.report-item:hover .report-arrow {
    transform: translateX(4px);
    color: var(--accent-primary);
}

/* ========== 状态徽章 - Apple 深色风格 ========== */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 0.25rem 0.5rem;
    border-radius: var(--radius-sm);
    font-family: var(--font-body);
    font-size: 0.625rem;
    font-weight: 600;
    letter-spacing: 0.02em;
}

.badge-success { background: rgba(50, 213, 131, 0.2); color: var(--green-success); }
.badge-warning { background: rgba(255, 181, 71, 0.2); color: var(--yellow-warning); }
.badge-danger { background: rgba(232, 90, 79, 0.2); color: var(--red-error); }
.badge-pending { background: var(--bg-elevated); color: var(--text-secondary); border: 1px solid var(--border-color); }

/* ========== 修复 Streamlit 警告和信息框 ========== */
.stAlert > div {
    color: var(--text-primary) !important;
    border-radius: var(--radius-md) !important;
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-color) !important;
}
.stAlert [data-testid="stMarkdownContainer"] p {
    color: var(--text-primary) !important;
}
div[data-baseweb="notification"] {
    color: var(--text-primary) !important;
    border-radius: var(--radius-md) !important;
    background: var(--bg-surface) !important;
}
div[data-baseweb="notification"] div {
    color: var(--text-primary) !important;
}

/* ========== 分类卡片 - Apple 深色风格 ========== */
.category-card {
    background: var(--bg-surface);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    border: 1px solid var(--border-color);
    margin-bottom: var(--space-lg);
}

.category-header {
    display: flex;
    align-items: center;
    gap: var(--space-sm);
    font-family: var(--font-heading);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-md);
    letter-spacing: -0.01em;
}

/* ========== 指标行 - Apple 深色风格 ========== */
.metric-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: var(--space-md) 0;
    border-bottom: 1px solid var(--border-color);
}

.metric-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
}

.metric-name {
    font-family: var(--font-heading);
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
    margin-bottom: var(--space-xs);
}

.metric-benchmark {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
}

.metric-compare-up {
    color: var(--green-success);
    font-size: 0.75rem;
    font-weight: 600;
}

.metric-compare-down {
    color: var(--red-error);
    font-size: 0.75rem;
    font-weight: 600;
}

.metric-value {
    font-family: var(--font-heading);
    font-size: 1.125rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}

/* ========== 风险卡片 - Apple 深色风格 ========== */
.risk-card {
    background: var(--bg-surface);
    border-radius: var(--radius-lg);
    padding: var(--space-lg);
    text-align: center;
    border: 1px solid var(--border-color);
}

.risk-label {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-bottom: var(--space-md);
    font-weight: 500;
}

.risk-value {
    font-family: var(--font-heading);
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.02em;
}

.risk-value.critical { color: var(--red-error); }
.risk-value.high { color: var(--yellow-warning); }
.risk-value.medium { color: var(--yellow-warning); }

.risk-sub {
    font-family: var(--font-body);
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-top: var(--space-sm);
}

/* ========== 上传区域 - Apple 深色风格 ========== */
.upload-area {
    border: 2px dashed var(--border-color);
    border-radius: var(--radius-lg);
    padding: var(--space-2xl) var(--space-xl);
    text-align: center;
    background: var(--bg-surface);
    margin: var(--space-lg) 0;
    transition: all 0.2s ease;
}

.upload-area:hover {
    border-color: var(--accent-primary);
    background: var(--bg-elevated);
}

.upload-icon {
    font-size: 2.5rem;
    color: var(--text-secondary);
    margin-bottom: var(--space-md);
}

.upload-text {
    font-family: var(--font-body);
    font-size: 0.875rem;
    color: var(--text-secondary);
}

/* ========== 搜索框 - Apple 深色风格 ========== */
.stTextInput > div > div > input {
    font-family: var(--font-body) !important;
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--border-color) !important;
    padding: 0.875rem 1rem !important;
    background: var(--bg-surface) !important;
    color: var(--text-primary) !important;
    font-size: 0.875rem !important;
    transition: all 0.2s ease !important;
}

.stTextInput > div > div > input:focus {
    border-color: var(--accent-primary) !important;
    box-shadow: 0 0 0 2px rgba(50, 213, 131, 0.2) !important;
}

.stTextInput > div > div > input::placeholder {
    color: var(--text-secondary) !important;
}

/* ========== 选择框 - Apple 深色风格 ========== */
.stSelectbox > div > div {
    border-radius: var(--radius-md) !important;
    border-color: var(--border-color) !important;
    background: var(--bg-surface) !important;
}

.stSelectbox [data-baseweb="select"] > div {
    background: var(--bg-surface) !important;
    border-color: var(--border-color) !important;
    color: var(--text-primary) !important;
}

.stMultiSelect > div > div {
    border-radius: var(--radius-md) !important;
    border-color: var(--border-color) !important;
    background: var(--bg-surface) !important;
}

.stMultiSelect [data-baseweb="select"] > div {
    background: var(--bg-surface) !important;
    color: var(--text-primary) !important;
}

/* ========== Tab 样式 - Apple 深色风格 ========== */
.stTabs [data-baseweb="tab-list"] {
    gap: var(--space-sm);
    background: transparent;
    border-radius: 0;
    padding: 0;
    border-bottom: 1px solid var(--border-color);
}

.stTabs [data-baseweb="tab"] {
    font-family: var(--font-heading);
    padding: 0.75rem 1rem;
    font-size: 0.875rem;
    color: var(--text-secondary);
    border-radius: var(--radius-sm) var(--radius-sm) 0 0;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    font-weight: 500;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-primary);
    background: var(--bg-elevated);
}

.stTabs [aria-selected="true"] {
    color: var(--text-primary) !important;
    background: transparent !important;
    border-bottom-color: var(--accent-primary) !important;
}

/* 分隔线 */
hr {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: var(--space-lg) 0;
}

/* 信息提示 */
.stAlert {
    border-radius: var(--radius-md) !important;
}

/* ========== 移动端适配 ========== */
@media (max-width: 768px) {
    /* 主内容区 */
    .main .block-container {
        padding: 1rem !important;
        max-width: 100% !important;
    }
    
    /* 页面标题 */
    .page-title {
        font-size: 1.25rem !important;
    }
    
    .page-desc {
        font-size: 0.8rem !important;
    }
    
    /* 统计卡片 */
    .stat-card {
        padding: 0.875rem 1rem !important;
    }
    
    .stat-value {
        font-size: 1.5rem !important;
    }
    
    .stat-header {
        font-size: 0.75rem !important;
    }
    
    .stat-sub {
        font-size: 0.7rem !important;
    }
    
    /* 报告列表项 */
    .report-item {
        padding: 0.875rem 1rem !important;
        gap: 0.75rem !important;
    }
    
    .report-icon {
        width: 36px !important;
        height: 36px !important;
        font-size: 1rem !important;
    }
    
    .report-title {
        font-size: 0.875rem !important;
    }
    
    .report-meta {
        font-size: 0.75rem !important;
    }
    
    /* 分类卡片 */
    .category-card {
        padding: 1rem !important;
    }
    
    .category-header {
        font-size: 0.875rem !important;
    }
    
    /* 指标卡片 */
    .metric-card {
        padding: 1rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    .metric-label {
        font-size: 0.75rem !important;
    }
    
    .metric-value {
        font-size: 1.5rem !important;
    }
    
    /* 风险卡片 */
    .risk-card {
        padding: 1rem !important;
    }
    
    .risk-value {
        font-size: 1.5rem !important;
    }
    
    /* 上传区域 */
    .upload-area {
        padding: 2rem 1rem !important;
    }
    
    .upload-icon {
        font-size: 2rem !important;
    }
    
    /* 表单控件：增大可点击区域（移动端 44px 触控标准） */
    .stButton > button {
        min-height: 46px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.95rem !important;
    }

    /* 按钮之间留白，避免误触 */
    div.stButton {
        margin-top: 0.5rem !important;
    }

    /* 输入框/选择器：避免 iOS 自动放大（font-size >= 16px） */
    .stTextInput input,
    .stTextArea textarea {
        min-height: 46px !important;
        font-size: 16px !important;
        line-height: 1.2 !important;
    }

    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        min-height: 46px !important;
        font-size: 16px !important;
    }

    /* 列布局在手机上堆叠为单列，避免一排太多小按钮/卡片 */
    .main .block-container [data-testid="stHorizontalBlock"] {
        flex-direction: column !important;
        gap: 0.75rem !important;
    }

    .main .block-container [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
    }
    
    /* Tab：支持横向滚动，避免挤压 */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        white-space: nowrap !important;
        scrollbar-width: none;
    }

    .stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {
        display: none;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.6rem 0.9rem !important;
        font-size: 0.9rem !important;
        flex: 0 0 auto !important;
    }
    
    /* 侧边栏 */
    [data-testid="stSidebar"] > div:first-child {
        padding: 1rem 0.75rem !important;
    }
    
    .sidebar-title {
        font-size: 0.9rem !important;
        margin-bottom: 1.5rem !important;
    }
}

/* 超小屏幕 */
@media (max-width: 480px) {
    .main .block-container {
        padding: 0.75rem !important;
        padding-top: 4rem !important;
    }

    /* 超小屏再加大按钮，提升可点性 */
    .stButton > button {
        min-height: 48px !important;
        font-size: 1rem !important;
    }
    
    .stat-value {
        font-size: 1.25rem !important;
    }
    
    .metric-value {
        font-size: 1.25rem !important;
    }
}

/* ========== 移动端整体优化 ========== */
@media (max-width: 768px) {
    /* 隐藏 Streamlit 默认 header/footer/menu */
    header[data-testid="stHeader"],
    footer,
    #MainMenu {
        display: none !important;
    }

    /* 页面标题简化 */
    h1 {
        font-size: 1.4rem !important;
        line-height: 1.3 !important;
        margin-bottom: 0.75rem !important;
    }
    h2 {
        font-size: 1.2rem !important;
        margin-bottom: 0.5rem !important;
    }
    h3 {
        font-size: 1.05rem !important;
    }

    /* 统计卡片移动端优化 */
    .stat-card {
        padding: 1rem !important;
        margin-bottom: 0.75rem !important;
    }
    .stat-card .stat-value {
        font-size: 1.5rem !important;
    }
    .stat-card .stat-header {
        font-size: 0.85rem !important;
    }

    /* 风险卡片 */
    .risk-card {
        padding: 0.75rem !important;
    }

    /* 报告项 */
    .report-item {
        padding: 0.875rem !important;
        margin-bottom: 0.5rem !important;
    }
    .report-item .report-title {
        font-size: 0.95rem !important;
    }

    /* 表格移动端：横向滚动 + 更紧凑 */
    .stDataFrame,
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    .stDataFrame table,
    [data-testid="stDataFrame"] table {
        font-size: 0.8rem !important;
        min-width: max-content !important;
    }
    .stDataFrame th,
    .stDataFrame td,
    [data-testid="stDataFrame"] th,
    [data-testid="stDataFrame"] td {
        padding: 0.4rem 0.5rem !important;
        white-space: nowrap !important;
    }

    /* Expander 折叠面板 */
    .streamlit-expanderHeader {
        font-size: 0.95rem !important;
        padding: 0.75rem !important;
    }
    .streamlit-expanderContent {
        padding: 0.75rem !important;
    }

    /* Markdown 内容 */
    .stMarkdown p {
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
    }
    .stMarkdown ul, .stMarkdown ol {
        padding-left: 1.25rem !important;
    }
    .stMarkdown li {
        margin-bottom: 0.4rem !important;
    }

    /* Alert/Info/Warning boxes */
    .stAlert {
        padding: 0.75rem !important;
        font-size: 0.9rem !important;
    }

    /* 文件上传区域 */
    [data-testid="stFileUploader"] {
        padding: 1rem !important;
    }
    [data-testid="stFileUploader"] section {
        padding: 1.5rem 1rem !important;
    }

    /* Metric 组件 */
    [data-testid="stMetric"] {
        padding: 0.5rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem !important;
    }

    /* Plotly 图表容器 */
    .stPlotlyChart {
        margin: 0 -0.5rem !important;
    }

    /* 进度条 */
    .stProgress > div {
        height: 8px !important;
    }

    /* 代码块 */
    .stCodeBlock {
        font-size: 0.75rem !important;
    }

    /* JSON 展示 */
    pre {
        font-size: 0.75rem !important;
        overflow-x: auto !important;
        white-space: pre !important;
    }
}

/* ========== 移动端固定顶部导航栏 ========== */
.mobile-nav-bar {
    display: none;
}

@media (max-width: 768px) {
    .mobile-nav-bar {
        display: flex !important;
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        background: var(--bg-surface);
        border-bottom: 1px solid var(--border-color);
        z-index: 999998;
        align-items: center;
        justify-content: space-between;
        padding: 0 1rem;
    }

    .mobile-nav-bar .nav-title {
        color: var(--text-primary);
        font-size: 1rem;
        font-weight: 600;
        flex: 1;
        text-align: center;
        margin: 0 0.5rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .mobile-nav-bar .nav-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        min-width: 44px;
        min-height: 44px;
        background: var(--bg-elevated);
        border: 1px solid var(--border-color);
        border-radius: var(--radius-md);
        color: var(--text-primary);
        font-size: 1.25rem;
        cursor: pointer;
        text-decoration: none;
        transition: all 0.2s;
    }

    .mobile-nav-bar .nav-btn:hover,
    .mobile-nav-bar .nav-btn:active {
        background: var(--accent-primary);
        border-color: var(--accent-primary);
    }

    /* 为固定导航栏留出空间 */
    .main .block-container {
        padding-top: 4.5rem !important;
        padding-bottom: calc(6.5rem + env(safe-area-inset-bottom)) !important;
    }

    /* 让 columns 在手机上自动换行，避免内容被挤压到不可用 */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 0.75rem !important;
    }
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 0 !important;
    }

    /* 底部导航按钮内部保持横排，不受全局 columns 堆叠规则影响 */
    .mobile-nav-buttons [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
        gap: 0.5rem !important;
        flex-direction: row !important;
    }
    .mobile-nav-buttons [data-testid="column"] {
        width: auto !important;
        flex: 1 1 auto !important;
        min-width: 0 !important;
    }

    /* 隐藏侧边栏展开按钮（用我们的导航栏代替） */
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }
}
</style>
"""


def inject_css():
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def render_sidebar():
    import streamlit as st
    st.markdown('<div class="sidebar-title">📊 财务分析专家</div>', unsafe_allow_html=True)


def render_sidebar_nav():
    """渲染侧边栏导航"""
    import streamlit as st
    render_sidebar()
    st.page_link("app.py", label="仪表盘", icon="📊")
    st.page_link("pages/1_股票查询.py", label="股票查询", icon="🔎")
    st.page_link("pages/2_上传报表.py", label="上传报表", icon="📁")
    st.page_link("pages/3_分析报告.py", label="分析报告", icon="📑")
    st.page_link("pages/4_财务指标.py", label="财务指标", icon="📈")
    st.page_link("pages/5_风险预警.py", label="风险预警", icon="🔔")
    st.page_link("pages/6_趋势分析.py", label="趋势分析", icon="📉")


def render_mobile_nav(title: str = "财务分析专家", show_back: bool = True, back_url: str = "app.py"):
    """渲染移动端固定底部导航栏（更稳定的实现，避免 iOS 交互问题）"""
    import streamlit as st
    
    # 顶部标题栏
    st.markdown(f'''
    <div class="mobile-nav-bar">
        <span class="nav-title">📊 {title}</span>
    </div>
    ''', unsafe_allow_html=True)
    
    # 底部固定导航栏样式
    st.markdown('''
    <style>
    @media (max-width: 768px) {
        /* 底部导航栏容器 */
        .mobile-bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-surface);
            border-top: 1px solid var(--border-color);
            padding: 0.5rem 0;
            padding-bottom: calc(0.5rem + env(safe-area-inset-bottom));
            z-index: 999998;
            display: flex;
            justify-content: space-around;
            align-items: center;
        }
        .mobile-bottom-nav .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.25rem;
            padding: 0.5rem 1rem;
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 0.7rem;
            border-radius: var(--radius-sm);
            transition: all 0.2s;
            min-width: 60px;
        }
        .mobile-bottom-nav .nav-item:active {
            background: var(--bg-elevated);
        }
        .mobile-bottom-nav .nav-item .nav-icon {
            font-size: 1.25rem;
        }
        
        /* 底部导航按钮区域 */
        .mobile-nav-buttons {
            position: fixed;
            bottom: calc(env(safe-area-inset-bottom) + 0.5rem);
            left: 0;
            right: 0;
            padding: 0 1rem;
            z-index: 999999;
            display: flex;
            justify-content: center;
            gap: 1rem;
            pointer-events: none;
        }
        .mobile-nav-buttons > div {
            pointer-events: auto;
        }
        .mobile-nav-buttons .stButton > button {
            min-width: 70px !important;
            min-height: 44px !important;
            border-radius: 22px !important;
            font-size: 0.85rem !important;
            padding: 0.5rem 1rem !important;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3) !important;
            background: var(--bg-surface) !important;
            color: var(--text-primary) !important;
            border: 1px solid var(--border-color) !important;
        }
        .mobile-nav-buttons .stButton > button:active {
            background: var(--bg-elevated) !important;
            transform: scale(0.98);
        }
    }
    @media (min-width: 769px) {
        .mobile-bottom-nav,
        .mobile-nav-buttons {
            display: none !important;
        }
    }
    </style>
    ''', unsafe_allow_html=True)
    
    # 简化的底部导航按钮（使用 Streamlit 原生按钮，放在页面底部）
    st.markdown('<div class="mobile-nav-buttons">', unsafe_allow_html=True)
    cols = st.columns([1, 1, 1, 1])
    with cols[0]:
        if st.button("← 返回", key=f"m_back_{title}"):
            st.switch_page(back_url)
    with cols[1]:
        if st.button("🏠 首页", key=f"m_home_{title}"):
            st.switch_page("app.py")
    with cols[2]:
        if st.button("🔎 查询", key=f"m_search_{title}"):
            st.switch_page("pages/1_股票查询.py")
    with cols[3]:
        if st.button("📑 报告", key=f"m_report_{title}"):
            st.switch_page("pages/3_分析报告.py")
    st.markdown('</div>', unsafe_allow_html=True)


def stat_card(label: str, value, sub: str = "", icon: str = "📄") -> str:
    return f'''
    <div class="stat-card">
        <div class="stat-header">
            <span>{icon}</span>
            <span>{label}</span>
        </div>
        <div class="stat-value">{value}</div>
        <div class="stat-sub">{sub}</div>
    </div>
    '''


def badge(text: str, status: str = "pending") -> str:
    return f'<span class="badge badge-{status}">{text}</span>'


def report_item(title: str, meta: str, status: str, status_text: str) -> str:
    return f'''
    <div class="report-item">
        <div class="report-icon">📄</div>
        <div class="report-info">
            <div class="report-title">{title} {badge(status_text, status)}</div>
            <div class="report-meta">{meta}</div>
        </div>
        <div class="report-arrow">›</div>
    </div>
    '''


def risk_card(label: str, value: int, sub: str, level: str = "medium") -> str:
    return f'''
    <div class="risk-card">
        <div class="risk-label">{label}</div>
        <div class="risk-value {level}">{value}</div>
        <div class="risk-sub">{sub}</div>
    </div>
    '''
