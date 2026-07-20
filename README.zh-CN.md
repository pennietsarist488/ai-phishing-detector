# AI钓鱼网站动态识别及防护系统

> 基于深度学习的实时钓鱼网站检测与防护系统，融合浏览器扩展、Python后端、CNN+BiLSTM模型与规则引擎，构建多层防御体系。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Chrome Extension](https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-green.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-ee4c2c.svg)](https://pytorch.org/)
[![Accuracy](https://img.shields.io/badge/准确率-98.97%25-brightgreen.svg)](#模型性能)

**中文** | **[English](README.md)**

---

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [模型性能](#模型性能)
- [快速开始](#快速开始)
- [安装部署](#安装部署)
- [使用说明](#使用说明)
- [API参考](#api参考)
- [模型训练](#模型训练)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [技术栈](#技术栈)
- [贡献指南](#贡献指南)
- [开源协议](#开源协议)
- [致谢](#致谢)
- [免责声明](#免责声明)

---

## 项目简介

AI钓鱼网站动态识别及防护系统是一个全栈安全解决方案，能够实时保护用户免受钓鱼攻击。系统采用**混合检测引擎**，融合以下三大模块：

- **规则引擎** — 10条静态规则，快速预筛URL
- **URL CNN+BiLSTM** — 字符级深度学习模型，分类URL合法性
- **表单分析器** — DOM级别检查敏感输入字段和表单提交行为

系统以 **Chrome/Edge浏览器扩展**（Manifest V3）形式运行，后端为 **Flask API服务**，在页面加载前拦截导航请求并阻断高风险钓鱼网站。

### 检测流程

```
用户访问URL → 扩展拦截导航请求
                  │
                  ▼
         后端规则引擎快速预筛
           │          │          │
        高风险      可疑      低风险
           │          │          │
           ▼          ▼          ▼
        阻断      混合检测     放行
                    │
       ┌────────────┼────────────┐
       ▼            ▼            ▼
   URL CNN     表单分析     品牌域名信任
       │            │            │
       └────────────┼────────────┘
                    ▼
           动态权重融合决策
                    │
                    ▼
                检测结果
```

---

## 核心特性

- **实时防护** — 通过 `webNavigation` API 在页面加载前拦截分析URL
- **三级分流** — 低风险（放行）→ 可疑（警告横幅）→ 高风险（阻断）
- **混合决策引擎** — 融合规则引擎(0.40)、CNN模型(0.40)、表单分析(0.20)
- **动态权重分配** — 某模块不可用时自动将权重按比例分配给其他模块
- **域名信任机制** — 对已知品牌域名降低CNN误报率
- **模型热重载** — 无需重启服务即可更新模型权重
- **双模式UI** — 普通模式（简洁）与专家模式（详细指标）
- **API限流** — 防止滥用（检测60次/分钟，批量10次/分钟）
- **Docker支持** — 容器化部署，内置健康检查
- **WebSocket支持** — 通过WebSocket协议实现实时检测

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│              浏览器扩展 (Manifest V3)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ 弹窗UI   │  │ 拦截页   │  │ background.js        │   │
│  │ (popup)  │  │(blocked) │  │ (导航拦截+通信)       │   │
│  └──────────┘  └──────────┘  └──────────┬───────────┘   │
│                                         │ HTTP/WS        │
└─────────────────────────────────────────┼────────────────┘
                                          │
┌─────────────────────────────────────────┼────────────────┐
│                 Python后端 (Flask)       │                │
│  ┌──────────────────────────────────────▼─────────────┐  │
│  │           API路由 + WebSocket                       │  │
│  └──────┬─────────────────────────────────────────────┘  │
│         │                                                │
│  ┌──────▼──────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ 规则引擎    │  │ 表单     │  │ 混合检测器         │  │
│  │ (10条规则)  │  │ 分析器   │  │ (规则+CNN+表单)    │  │
│  └─────────────┘  └──────────┘  └─────────┬──────────┘  │
│                                          │              │
│  ┌───────────────────────────────────────▼────────────┐ │
│  │         URL CNN+BiLSTM + 页面截图器                 │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## 模型性能

基于 [PhiUSIIL Phishing URL Dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset) 训练和评估：

| 指标 | 数值 |
|------|------|
| **准确率 (Accuracy)** | 98.97% |
| **精确率 (Precision)** | 99.28% |
| **召回率 (Recall)** | 98.31% |
| **F1分数 (F1 Score)** | 98.79% |
| **AUC-ROC** | 0.9988 |

- **测试样本**：35,306条URL（15,078条钓鱼，20,228条合法）
- **误报率**：0.53%（108个合法网站被误判）
- **漏报率**：1.69%（255个钓鱼网站被漏判）

---

## 快速开始

### 环境要求

- Python 3.10+
- Chrome 或 Edge 浏览器（支持开发者模式）
- 建议 8GB+ 内存

### 1. 克隆并安装后端

```bash
git clone https://github.com/cheng-jun-hao/ai-phishing-detector.git
cd phishing-detector
pip install -r requirements.txt

# 安装 Playwright 浏览器（用于表单分析）
playwright install chromium
```

### 2. 启动后端服务

```bash
# 方式一：直接运行
python -m backend.app

# 方式二：Docker部署
docker-compose up -d --build
```

服务地址：
- HTTP API：`http://127.0.0.1:5000/api`
- 健康检查：`http://127.0.0.1:5000/api/health`
- WebSocket：`ws://127.0.0.1:5000/ws`

### 3. 加载浏览器扩展

1. 打开 Chrome/Edge，访问 `chrome://extensions/`
2. 开启右上角的 **开发者模式**
3. 点击 **加载已解压的扩展程序**
4. 选择 `extension/` 目录

### 4. 开始检测

- 点击工具栏扩展图标，手动检测URL
- 正常浏览时，高风险钓鱼网站会被自动阻断
- 可疑网站会在页面顶部显示黄色警告横幅

---

## 安装部署

### 后端依赖

项目所需Python包（见 [`requirements.txt`](requirements.txt)）：

| 类别 | 依赖包 |
|------|--------|
| Web框架 | Flask, Flask-CORS, Flask-SocketIO |
| AI/ML | PyTorch, NumPy, Pandas, scikit-learn |
| 浏览器自动化 | Playwright |
| HTML解析 | BeautifulSoup4 |
| 字符串匹配 | python-Levenshtein |
| 生产环境 | Gunicorn, psutil |

### Docker部署

```bash
# 构建并启动
docker-compose up -d --build

# 查看日志
docker-compose logs -f backend

# 停止
docker-compose down

# 热重载模型
curl -X POST http://localhost:5000/api/model/reload
```

---

## 使用说明

### 手动检测（弹窗）

1. 点击工具栏中的扩展图标
2. 输入URL或使用当前页面的URL
3. 点击 **检测** 按钮
4. 查看结果：
   - **普通模式**：风险等级和简要说明
   - **专家模式**：详细评分、命中规则、AI置信度

### 实时防护

- 默认开启
- 自动阻断高风险钓鱼网站
- 对可疑网站显示警告横幅
- 允许安全网站正常加载

### 设置

- 切换 普通/专家 模式
- 启用/禁用实时检测
- 配置后端服务地址
- 查看检测历史记录

---

## API参考

| 方法 | 端点 | 说明 | 限流 |
|------|------|------|------|
| `POST` | `/api/detect` | 单URL检测 | 60次/分钟 |
| `POST` | `/api/detect-batch` | 批量检测（最多20个） | 10次/分钟 |
| `GET` | `/api/health` | 健康检查（含系统指标） | — |
| `GET` | `/api/model/info` | 模型状态和架构信息 | — |
| `POST` | `/api/model/reload` | 热重载模型（仅限本地） | — |
| `WS` | `/ws` | WebSocket实时检测 | — |

### 请求示例

```bash
curl -X POST http://127.0.0.1:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{"url": "https://login-verify-account.tk/update"}'
```

### 响应示例

```json
{
  "url": "https://login-verify-account.tk/update",
  "is_phishing": true,
  "final_risk_score": 70.0,
  "risk_level": "high",
  "rule_result": {
    "rule_score": 70,
    "matched_rules": [
      {"rule": "suspicious_keywords", "detail": "URL contains suspicious keywords: login, verify, update, account"},
      {"rule": "suspicious_tld", "detail": "URL uses suspicious TLD: .tk"}
    ]
  },
  "url_cnn_result": {
    "phishing_confidence": 0.72,
    "prediction": "phishing",
    "model_loaded": true
  },
  "recommendation": "Rule engine classified as high risk, recommend immediate blocking"
}
```

---

## 模型训练

### 训练URL CNN+BiLSTM模型

```bash
# 先下载 PhiUSIIL 数据集
# https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset

python training/train_url_cnn.py \
  --data path/to/PhiUSIIL_Phishing_URL_Dataset.csv \
  --epochs 20 \
  --batch_size 128 \
  --output models/url_cnn.pth
```

### 评估模型

```bash
python training/evaluate.py \
  --data path/to/PhiUSIIL_Phishing_URL_Dataset.csv \
  --model models/url_cnn.pth
```

### 数据增强策略

训练流程包含三种数据增强技术：

1. **通用增强** — 随机移除 `www`、切换 HTTP/HTTPS、截断查询参数
2. **合法URL路径增强** — 为短合法URL添加常见路径/查询，平衡结构分布
3. **钓鱼URL HTTPS增强** — 为HTTP钓鱼URL创建HTTPS变体

### 融合权重

| 模块 | 权重 | 说明 |
|------|------|------|
| 规则引擎 | 0.40 | 快速静态规则预筛 |
| URL CNN+BiLSTM | 0.40 | 深度学习URL特征分析 |
| 表单分析 | 0.20 | DOM表单敏感字段检测 |

> **动态分配**：当某模块不可用（如CNN未加载）时，其权重会按比例分配给其他模块。

---

## 配置说明

所有配置项均支持环境变量覆盖：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `BACKEND_HOST` | `127.0.0.1` | 服务监听地址 |
| `BACKEND_PORT` | `5000` | 服务端口 |
| `DEBUG` | `false` | 调试模式 |
| `SECRET_KEY` | *(开发默认值)* | Flask密钥（**生产环境必须修改**） |
| `MODEL_DIR` | `../models` | 模型文件目录 |
| `URL_CNN_MODEL_PATH` | `models/url_cnn.pth` | CNN模型权重路径 |
| `PAGE_LOAD_TIMEOUT` | `15` | 页面加载超时（秒） |
| `RULE_HIGH_RISK_THRESHOLD` | `60` | 高风险分数阈值 |
| `RULE_LOW_RISK_THRESHOLD` | `30` | 低风险分数阈值 |
| `RULE_WEIGHT` | `0.40` | 规则引擎融合权重 |
| `URL_CNN_WEIGHT` | `0.40` | CNN融合权重 |
| `FORM_WEIGHT` | `0.20` | 表单分析融合权重 |

---

## 项目结构

```
phishing-detector/
├── extension/                    # 浏览器扩展 (Manifest V3)
│   ├── manifest.json             # 扩展配置
│   ├── popup.html / popup.js     # 弹窗UI（双模式）
│   ├── popup.css                 # 弹窗样式
│   ├── background.js             # Service Worker（导航拦截）
│   ├── content.js                # 内容脚本（警告横幅+表单监控）
│   ├── blocked.html / blocked.js # 阻断警告页
│   ├── settings.html / settings.js # 设置页
│   └── assets/
│       └── icon.svg              # 矢量图标
│
├── backend/                      # Python后端
│   ├── app.py                    # 服务入口
│   ├── api/
│   │   ├── routes.py             # API路由 + WebSocket
│   │   └── __init__.py           # API模块文档
│   ├── engine/
│   │   ├── rule_engine.py        # 规则引擎（10条检测规则）
│   │   ├── form_analyzer.py      # 表单分析器
│   │   ├── screenshotter.py      # 无头浏览器页面提取器
│   │   └── __init__.py           # 引擎模块文档
│   ├── models/
│   │   ├── url_cnn.py            # URL字符级CNN+BiLSTM
│   │   ├── hybrid_model.py       # 混合决策模型
│   │   └── __init__.py           # 模型模块文档
│   └── utils/
│       ├── config.py             # 全局配置（支持环境变量）
│       ├── middleware.py         # 中间件（限流、日志）
│       ├── url_utils.py          # URL工具函数
│       └── __init__.py           # 工具模块文档
│
├── training/                     # 模型训练
│   ├── train_url_cnn.py          # URL CNN训练脚本
│   ├── evaluate.py               # 模型评估脚本
│   └── __init__.py               # 训练模块文档
│
├── models/                       # 模型文件
│   └── url_cnn.pth               # URL CNN权重
│
├── .gitignore                    # Git忽略规则
├── Dockerfile                    # Docker容器配置
├── docker-compose.yml            # Docker Compose配置
├── requirements.txt              # Python依赖
├── LICENSE                       # MIT许可证
├── CONTRIBUTING.md               # 贡献指南
├── README.md                     # 英文文档
└── README.zh-CN.md               # 中文文档（本文件）
```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 浏览器扩展 | Manifest V3, Chrome Extensions API, Shadow DOM |
| 后端 | Flask, Flask-SocketIO, Flask-CORS |
| 深度学习 | PyTorch, CNN, BiLSTM |
| 浏览器自动化 | Playwright (Chromium) |
| HTML解析 | BeautifulSoup4 |
| 字符串匹配 | python-Levenshtein |
| 部署 | Docker, Docker Compose |
| 监控 | psutil |

---

## 规则引擎检测项

| 规则 | 权重 | 说明 |
|------|------|------|
| IP代替域名 | 20 | URL中使用IP地址而非域名 |
| 可疑关键词 | 15/个 | login/verify/update/account等 |
| 域名相似度 | 15 | 与已知品牌的编辑距离 |
| URL过长 | 10 | 超过75个字符 |
| 可疑顶级域 | 15 | .tk/.ml/.ga/.xyz等 |
| 特殊字符比例 | 10 | 超过15% |
| 无HTTPS | 10 | 明文HTTP协议 |
| @符号 | 20 | URL欺骗攻击 |
| 双斜杠重定向 | 15 | 重定向攻击 |
| 子域名过多 | 10 | 超过3级 |

## 风险等级分类

| 分数范围 | 风险等级 | 处置方式 |
|----------|----------|----------|
| 0–30 | 低风险 | 放行 |
| 31–59 | 可疑 | 显示警告横幅 |
| 60–100 | 高风险 | 阻断 |

---

## 贡献指南

欢迎贡献代码！请先阅读 [贡献指南](CONTRIBUTING.md)。

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 发起 Pull Request

---

## 开源协议

本项目基于 MIT 协议开源 — 详见 [LICENSE](LICENSE) 文件。

---

## 致谢

- **数据集**：[PhiUSIIL Phishing URL Dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset)（UCI机器学习仓库）
- **灵感来源**：现代浏览器安全扩展及钓鱼检测学术研究
- **技术栈**：PyTorch, Flask, Playwright, Chrome Extensions API

---

## 免责声明

本软件仅供**教育和研究目的**使用。虽然在测试中达到较高的检测准确率，但没有任何钓鱼检测系统能保证100%有效。用户应保持警惕，不应仅依赖本工具做出安全决策。作者不对因使用本软件而造成的任何损害或损失承担责任。

---

**版本**：1.0.0 | **协议**：MIT | **作者**：cheng-jun-hao
