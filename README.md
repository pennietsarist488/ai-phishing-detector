# AI Phishing Website Detector

> A real-time phishing website detection and protection system powered by deep learning, combining a browser extension, Python backend, and CNN+BiLSTM model with a rule engine for multi-layered defense.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Chrome Extension](https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-green.svg)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-ee4c2c.svg)](https://pytorch.org/)
[![Accuracy](https://img.shields.io/badge/Accuracy-98.97%25-brightgreen.svg)](#model-performance)

**[中文文档](README.zh-CN.md)** | **English**

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Model Performance](#model-performance)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Model Training](#model-training)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)
- [Disclaimer](#disclaimer)

---

## Overview

AI Phishing Website Detector is a full-stack security solution that protects users from phishing attacks in real time. It leverages a **hybrid detection engine** that combines:

- **Rule Engine** — 10 static rules for fast URL pre-screening
- **URL CNN+BiLSTM** — Character-level deep learning model for URL classification
- **Form Analyzer** — DOM-level inspection of sensitive input fields and form actions

The system operates as a **Chrome/Edge browser extension** (Manifest V3) backed by a **Flask API server**, intercepting navigation requests and blocking high-risk phishing sites before they load.

### Detection Pipeline

```
User visits URL → Extension intercepts navigation
                      │
                      ▼
           Backend Rule Engine fast pre-screen
             │            │            │
          High Risk    Suspicious    Low Risk
             │            │            │
             ▼            ▼            ▼
        Block          Hybrid        Allow
                      Detection
                        │
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     URL CNN       Form Analysis   Brand Trust
         │              │              │
         └──────────────┼──────────────┘
                        ▼
              Dynamic Weight Fusion
                        │
                        ▼
                 Detection Result
```

---

## Key Features

- **Real-time Protection** — Intercepts and analyzes URLs before page load via `webNavigation` API
- **Three-tier Triage** — Low risk (allow) → Suspicious (warning banner) → High risk (block)
- **Hybrid Decision Engine** — Fuses rule engine (0.40), CNN model (0.40), and form analysis (0.20)
- **Dynamic Weight Allocation** — Automatically redistributes weights when a module is unavailable
- **Domain Trust Mechanism** — Reduces CNN false positives for known brand domains
- **Model Hot Reload** — Update model weights without restarting the service
- **Dual-mode UI** — Normal mode (simple) and Expert mode (detailed metrics)
- **API Rate Limiting** — Protects against abuse (60 req/min for detect, 10 req/min for batch)
- **Docker Support** — Containerized deployment with health checks
- **WebSocket Support** — Real-time detection via WebSocket protocol

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              Browser Extension (Manifest V3)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ popup UI │  │ blocked  │  │ background.js        │   │
│  │ (popup)  │  │ (block)  │  │ (nav intercept+comm) │   │
│  └──────────┘  └──────────┘  └──────────┬───────────┘   │
│                                         │ HTTP/WS        │
└─────────────────────────────────────────┼────────────────┘
                                          │
┌─────────────────────────────────────────┼────────────────┐
│                 Python Backend (Flask)  │                │
│  ┌──────────────────────────────────────▼─────────────┐  │
│  │           API Routes + WebSocket                   │  │
│  └──────┬─────────────────────────────────────────────┘  │
│         │                                                │
│  ┌──────▼──────┐  ┌──────────┐  ┌────────────────────┐  │
│  │ Rule Engine │  │ Form     │  │ Hybrid Detector    │  │
│  │ (10 rules)  │  │ Analyzer │  │ (Rule+CNN+Form)    │  │
│  └─────────────┘  └──────────┘  └─────────┬──────────┘  │
│                                          │              │
│  ┌───────────────────────────────────────▼────────────┐ │
│  │         URL CNN+BiLSTM + Screenshotter             │ │
│  └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

---

## Model Performance

Trained and evaluated on the [PhiUSIIL Phishing URL Dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset):

| Metric | Value |
|--------|-------|
| **Accuracy** | 98.97% |
| **Precision** | 99.28% |
| **Recall** | 98.31% |
| **F1 Score** | 98.79% |
| **AUC-ROC** | 0.9988 |

- **Test samples**: 35,306 URLs (15,078 phishing, 20,228 legitimate)
- **False Positive Rate**: 0.53% (108 legitimate sites misclassified)
- **False Negative Rate**: 1.69% (255 phishing sites missed)

---

## Quick Start

### Prerequisites

- Python 3.10+
- Chrome or Edge browser (with Developer Mode support)
- 8GB+ RAM recommended

### 1. Clone and Install Backend

```bash
git clone https://github.com/cheng-jun-hao/ai-phishing-detector.git
cd phishing-detector
pip install -r requirements.txt

# Install Playwright browser for form analysis
playwright install chromium
```

### 2. Start the Backend Service

```bash
# Option A: Run directly
python -m backend.app

# Option B: Docker deployment
docker-compose up -d --build
```

The service will be available at:
- HTTP API: `http://127.0.0.1:5000/api`
- Health check: `http://127.0.0.1:5000/api/health`
- WebSocket: `ws://127.0.0.1:5000/ws`

### 3. Load the Browser Extension

1. Open Chrome/Edge and navigate to `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` directory

### 4. Start Detecting

- Click the extension icon to manually check a URL
- Browse normally — high-risk phishing sites are blocked automatically
- Suspicious sites show a yellow warning banner at the top

---

## Installation

### Backend Dependencies

The project requires the following Python packages (see [`requirements.txt`](requirements.txt)):

| Category | Packages |
|----------|----------|
| Web Framework | Flask, Flask-CORS, Flask-SocketIO |
| AI/ML | PyTorch, NumPy, Pandas, scikit-learn |
| Browser Automation | Playwright |
| HTML Parsing | BeautifulSoup4 |
| String Matching | python-Levenshtein |
| Production | Gunicorn, psutil |

### Docker Deployment

```bash
# Build and start
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Stop
docker-compose down

# Hot reload model
curl -X POST http://localhost:5000/api/model/reload
```

---

## Usage

### Manual Detection (Popup)

1. Click the extension icon in the toolbar
2. Enter a URL or use the current page's URL
3. Click **Detect**
4. View results:
   - **Normal mode**: Risk level and brief description
   - **Expert mode**: Detailed scores, matched rules, AI confidence

### Real-time Protection

- Enabled by default
- Automatically blocks high-risk phishing sites
- Shows warning banners for suspicious sites
- Allows safe sites to load normally

### Settings

- Toggle between Normal/Expert mode
- Enable/disable real-time detection
- Configure backend service URL
- View detection history

---

## API Reference

| Method | Endpoint | Description | Rate Limit |
|--------|----------|-------------|------------|
| `POST` | `/api/detect` | Single URL detection | 60/min |
| `POST` | `/api/detect-batch` | Batch URL detection (max 20) | 10/min |
| `GET` | `/api/health` | Health check with system metrics | — |
| `GET` | `/api/model/info` | Model status and architecture | — |
| `POST` | `/api/model/reload` | Hot reload model (localhost only) | — |
| `WS` | `/ws` | WebSocket real-time detection | — |

### Example Request

```bash
curl -X POST http://127.0.0.1:5000/api/detect \
  -H "Content-Type: application/json" \
  -d '{"url": "https://login-verify-account.tk/update"}'
```

### Example Response

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

## Model Training

### Train the URL CNN+BiLSTM Model

```bash
# Download the PhiUSIIL dataset first
# https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset

python training/train_url_cnn.py \
  --data path/to/PhiUSIIL_Phishing_URL_Dataset.csv \
  --epochs 20 \
  --batch_size 128 \
  --output models/url_cnn.pth
```

### Evaluate the Model

```bash
python training/evaluate.py \
  --data path/to/PhiUSIIL_Phishing_URL_Dataset.csv \
  --model models/url_cnn.pth
```

### Data Augmentation Strategies

The training pipeline includes three augmentation techniques:

1. **General augmentation** — Randomly removes `www`, switches HTTP/HTTPS, truncates query parameters
2. **Legitimate URL path augmentation** — Adds common paths/queries to short legitimate URLs to balance structural distribution
3. **Phishing URL HTTPS augmentation** — Creates HTTPS variants of HTTP phishing URLs

### Fusion Weights

| Module | Weight | Description |
|--------|--------|-------------|
| Rule Engine | 0.40 | Fast static rule pre-screening |
| URL CNN+BiLSTM | 0.40 | Deep learning URL feature analysis |
| Form Analysis | 0.20 | DOM form sensitive field detection |

> **Dynamic allocation**: When a module is unavailable (e.g., CNN not loaded), its weight is redistributed proportionally to the remaining modules.

---

## Configuration

All configuration items support environment variable overrides:

| Variable | Default | Description |
|----------|---------|-------------|
| `BACKEND_HOST` | `127.0.0.1` | Service listen address |
| `BACKEND_PORT` | `5000` | Service port |
| `DEBUG` | `false` | Debug mode |
| `SECRET_KEY` | *(dev default)* | Flask secret key (**must set in production**) |
| `MODEL_DIR` | `../models` | Model file directory |
| `URL_CNN_MODEL_PATH` | `models/url_cnn.pth` | CNN model weight path |
| `PAGE_LOAD_TIMEOUT` | `15` | Page load timeout (seconds) |
| `RULE_HIGH_RISK_THRESHOLD` | `60` | High risk score threshold |
| `RULE_LOW_RISK_THRESHOLD` | `30` | Low risk score threshold |
| `RULE_WEIGHT` | `0.40` | Rule engine fusion weight |
| `URL_CNN_WEIGHT` | `0.40` | CNN fusion weight |
| `FORM_WEIGHT` | `0.20` | Form analysis fusion weight |

---

## Project Structure

```
phishing-detector/
├── extension/                    # Browser extension (Manifest V3)
│   ├── manifest.json             # Extension configuration
│   ├── popup.html / popup.js     # Popup UI (dual-mode)
│   ├── popup.css                 # Popup styles
│   ├── background.js             # Service Worker (navigation intercept)
│   ├── content.js                # Content script (warning banner + form monitor)
│   ├── blocked.html / blocked.js # Block warning page
│   ├── settings.html / settings.js # Settings page
│   └── assets/
│       └── icon.svg              # Vector icon
│
├── backend/                      # Python backend
│   ├── app.py                    # Service entry point
│   ├── api/
│   │   ├── routes.py             # API routes + WebSocket
│   │   └── __init__.py           # API module docs
│   ├── engine/
│   │   ├── rule_engine.py        # Rule engine (10 detection rules)
│   │   ├── form_analyzer.py      # Form analyzer
│   │   ├── screenshotter.py      # Headless browser page extractor
│   │   └── __init__.py           # Engine module docs
│   ├── models/
│   │   ├── url_cnn.py            # URL char-level CNN+BiLSTM
│   │   ├── hybrid_model.py       # Hybrid decision model
│   │   └── __init__.py           # Model module docs
│   └── utils/
│       ├── config.py             # Global config (env var support)
│       ├── middleware.py         # Middleware (rate limiting, logging)
│       ├── url_utils.py          # URL utility functions
│       └── __init__.py           # Utils module docs
│
├── training/                     # Model training
│   ├── train_url_cnn.py          # URL CNN training script
│   ├── evaluate.py               # Model evaluation script
│   └── __init__.py               # Training module docs
│
├── models/                       # Model files
│   └── url_cnn.pth               # URL CNN weights
│
├── .gitignore                    # Git ignore rules
├── Dockerfile                    # Docker container config
├── docker-compose.yml            # Docker Compose config
├── requirements.txt              # Python dependencies
├── LICENSE                       # MIT License
├── CONTRIBUTING.md               # Contribution guidelines
├── README.md                     # This file (English)
└── README.zh-CN.md               # Chinese documentation
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Browser Extension | Manifest V3, Chrome Extensions API, Shadow DOM |
| Backend | Flask, Flask-SocketIO, Flask-CORS |
| Deep Learning | PyTorch, CNN, BiLSTM |
| Browser Automation | Playwright (Chromium) |
| HTML Parsing | BeautifulSoup4 |
| String Matching | python-Levenshtein |
| Deployment | Docker, Docker Compose |
| Monitoring | psutil |

---

## Rule Engine Detection Items

| Rule | Weight | Description |
|------|--------|-------------|
| IP instead of domain | 20 | Uses IP address instead of domain name |
| Suspicious keywords | 15/each | login/verify/update/account etc. |
| Domain similarity | 15 | Edit distance to known brands |
| URL too long | 10 | Exceeds 75 characters |
| Suspicious TLD | 15 | .tk/.ml/.ga/.xyz etc. |
| Special char ratio | 10 | Exceeds 15% |
| No HTTPS | 10 | Plaintext HTTP protocol |
| @ symbol | 20 | URL spoofing attack |
| Double slash redirect | 15 | Redirect attack |
| Too many subdomains | 10 | More than 3 levels |

## Risk Level Classification

| Score Range | Risk Level | Action |
|-------------|-----------|--------|
| 0–30 | Low | Allow |
| 31–59 | Suspicious | Show warning banner |
| 60–100 | High | Block |

---

## Contributing

Contributions are welcome! Please read the [Contributing Guidelines](CONTRIBUTING.md) first.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- **Dataset**: [PhiUSIIL Phishing URL Dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset) from UCI Machine Learning Repository
- **Inspiration**: Modern browser security extensions and academic research on phishing detection
- **Tech Stack**: PyTorch, Flask, Playwright, Chrome Extensions API

---

## Disclaimer

This software is provided for **educational and research purposes only**. While it achieves high detection accuracy in testing, no phishing detection system is 100% effective. Users should remain vigilant and not rely solely on this tool for security decisions. The authors are not responsible for any damages or losses resulting from the use of this software.

---

**Version**: 1.0.0 | **License**: MIT | **Author**: cheng-jun-hao
