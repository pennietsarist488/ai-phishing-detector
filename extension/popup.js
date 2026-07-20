/**
 * popup.js - AI钓鱼检测系统弹窗逻辑
 * 双模式UI：普通用户模式 / 专业用户模式
 * 管理检测流程、模式切换、历史显示
 */
(function () {
  "use strict";

  // ============================================================
  // 状态管理
  // ============================================================

  /** 当前应用状态 */
  const state = {
    currentMode: "normal",        // "normal" | "expert"
    isRealTimeEnabled: true,
    backendUrl: "http://127.0.0.1:5000",
    lastResult: null,
    isBackendOnline: false
  };

  // ============================================================
  // DOM 元素引用
  // ============================================================

  const elements = {
    // 头部
    headerStatus: document.getElementById("header-status"),
    statusDot: document.querySelector(".status-dot"),

    // 输入
    urlInput: document.getElementById("url-input"),
    btnDetect: document.getElementById("btn-detect"),
    btnLoadingSpinner: document.getElementById("btn-loading-spinner"),
    inputError: document.getElementById("input-error"),

    // 结果区域
    resultNormal: document.getElementById("result-normal"),
    resultExpert: document.getElementById("result-expert"),
    loadingSection: document.getElementById("loading-section"),
    errorSection: document.getElementById("error-section"),

    // 普通模式
    resultCard: document.getElementById("result-card"),
    riskIconEmoji: document.getElementById("risk-icon-emoji"),
    riskBadge: document.getElementById("risk-badge"),
    riskDescription: document.getElementById("risk-description"),
    riskSummary: document.getElementById("risk-summary"),
    btnSwitchExpert: document.getElementById("btn-switch-expert"),

    // 专业模式
    expertScoreValue: document.getElementById("expert-score-value"),
    expertProgressFill: document.getElementById("expert-progress-fill"),
    expertRuleContent: document.getElementById("expert-rule-content"),
    expertAiContent: document.getElementById("expert-ai-content"),
    expertUrlCnnContent: document.getElementById("expert-url-cnn-content"),
    expertFormContent: document.getElementById("expert-form-content"),
    expertDetailsContent: document.getElementById("expert-details-content"),
    btnSwitchNormal: document.getElementById("btn-switch-normal"),

    // 错误
    errorText: document.getElementById("error-text"),

    // 历史
    historySection: document.getElementById("history-section"),
    historyList: document.getElementById("history-list"),
    btnClearHistory: document.getElementById("btn-clear-history"),

    // 底部工具栏
    btnSettings: document.getElementById("btn-settings"),
    btnHistory: document.getElementById("btn-history"),
    btnModeToggle: document.getElementById("btn-mode-toggle"),
    btnModeText: document.getElementById("btn-mode-text")
  };

  // ============================================================
  // 初始化
  // ============================================================

  /**
   * 弹窗初始化
   */
  async function init() {
    // 加载设置
    await loadSettings();

    // 检查后端状态
    await checkBackendStatus();

    // 获取当前标签页URL并填入输入框
    await fillCurrentTabUrl();

    // 绑定事件
    bindEvents();

    // 恢复上次的检测结果（如果有）
    if (state.lastResult) {
      renderResult(state.lastResult);
    }

    // 更新模式切换按钮文字
    updateModeButtonText();
  }

  /**
   * 从chrome.storage加载设置
   */
  async function loadSettings() {
    try {
      const response = await chrome.runtime.sendMessage({ action: "get_settings" });
      if (response.success && response.data) {
        const settings = response.data;
        state.currentMode = settings.userMode || "normal";
        state.isRealTimeEnabled = settings.realTimeEnabled !== false;
        state.backendUrl = settings.backendUrl || "http://127.0.0.1:5000";
      }
    } catch (error) {
      console.warn("[弹窗] 加载设置失败:", error.message);
    }
  }

  /**
   * 检查后端连接状态
   */
  async function checkBackendStatus() {
    try {
      const response = await chrome.runtime.sendMessage({
        action: "check_backend_health"
      });
      if (response.success && response.data) {
        state.isBackendOnline = response.data.healthy;
      }
    } catch (error) {
      state.isBackendOnline = false;
    }
    updateStatusIndicator();
  }

  /**
   * 获取当前标签页URL并填入输入框
   */
  async function fillCurrentTabUrl() {
    try {
      const tabs = await chrome.tabs.query({
        active: true,
        currentWindow: true
      });
      if (tabs && tabs.length > 0 && tabs[0].url) {
        const url = tabs[0].url;
        // 不自动填入浏览器内部页面
        if (!url.startsWith("chrome://") &&
            !url.startsWith("chrome-extension://") &&
            !url.startsWith("edge://")) {
          elements.urlInput.value = url;
        }
      }
    } catch (error) {
      console.warn("[弹窗] 获取当前标签页URL失败:", error.message);
    }
  }

  /**
   * 更新状态指示器
   */
  function updateStatusIndicator() {
    if (state.isBackendOnline) {
      elements.statusDot.classList.remove("offline", "warning");
      elements.headerStatus.textContent = "后端已连接";
    } else {
      elements.statusDot.classList.add("offline");
      elements.statusDot.classList.remove("warning");
      elements.headerStatus.textContent = "后端未连接";
    }
  }

  // ============================================================
  // 事件绑定
  // ============================================================

  function bindEvents() {
    // 检测按钮
    elements.btnDetect.addEventListener("click", handleDetect);
    // 回车键检测
    elements.urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleDetect();
    });

    // 模式切换 - 切换至专业模式
    elements.btnSwitchExpert.addEventListener("click", () => {
      switchMode("expert");
    });
    // 模式切换 - 切换至普通模式
    elements.btnSwitchNormal.addEventListener("click", () => {
      switchMode("normal");
    });

    // 底部工具栏
    elements.btnSettings.addEventListener("click", openSettings);
    elements.btnHistory.addEventListener("click", toggleHistory);
    elements.btnModeToggle.addEventListener("click", toggleMode);
    elements.btnClearHistory.addEventListener("click", clearHistory);
  }

  // ============================================================
  // 手动检测流程
  // ============================================================

  /**
   * 处理检测按钮点击
   */
  async function handleDetect() {
    const url = elements.urlInput.value.trim();

    // 验证URL格式
    if (!url) {
      showInputError("请输入要检测的网址");
      return;
    }

    if (!isValidUrl(url)) {
      showInputError("请输入有效的网址（以 http:// 或 https:// 开头）");
      return;
    }

    // 清除错误
    hideInputError();

    // 显示加载状态
    showLoading();

    try {
      // 发送检测请求给background
      const response = await chrome.runtime.sendMessage({
        action: "manual_detect",
        url: url
      });

      hideLoading();

      if (response.success) {
        state.lastResult = response.data;
        renderResult(response.data);
      } else {
        showError(response.error || "检测失败，请检查后端服务是否运行");
      }
    } catch (error) {
      hideLoading();
      showError("无法连接到检测服务，请确认后端已启动");
      console.error("[弹窗] 检测失败:", error.message);
    }
  }

  // ============================================================
  // 结果渲染
  // ============================================================

  /**
   * 根据当前模式渲染检测结果
   * @param {Object} result - 检测结果
   */
  function renderResult(result) {
    // 隐藏历史和错误
    elements.historySection.classList.add("hidden");
    elements.errorSection.classList.add("hidden");

    if (state.currentMode === "expert") {
      renderExpertResult(result);
    } else {
      renderNormalResult(result);
    }
  }

  /**
   * 渲染普通模式结果
   * @param {Object} result - 检测结果
   */
  function renderNormalResult(result) {
    elements.resultExpert.style.display = "none";
    elements.resultNormal.style.display = "block";

    const riskLevel = result.risk_level || "unknown";
    const isPhishing = result.is_phishing;

    // 风险等级图标
    const iconMap = {
      high: "🔴",
      suspicious: "🟡",
      low: "🟢",
      safe: "🟢",
      unknown: "⚪"
    };
    elements.riskIconEmoji.textContent = iconMap[riskLevel] || "⚪";

    // 风险等级徽章
    const labelMap = {
      high: "⚠️ 高风险 - 钓鱼网站",
      suspicious: "⚠️ 可疑网站",
      low: "✅ 低风险",
      safe: "✅ 安全",
      unknown: "❓ 未知"
    };
    elements.riskBadge.textContent = labelMap[riskLevel] || "❓ 未知";
    elements.riskBadge.className = "risk-badge " + getRiskBadgeClass(riskLevel);

    // 风险描述
    elements.riskDescription.textContent = result.message ||
      (isPhishing ? "检测到钓鱼网站特征，建议立即关闭" : "未检测到明显的钓鱼特征");

    // 简要信息
    elements.riskSummary.innerHTML = `
      <div style="display:flex;justify-content:space-between;font-size:12px;">
        <span>风险评分：</span>
        <strong>${result.risk_score || 0}/100</strong>
      </div>
      ${result.error ? `<div style="color:#ea4335;font-size:11px;margin-top:4px;">${escapeHTML(result.error)}</div>` : ""}
    `;

    // 更新结果卡片颜色
    const card = elements.resultCard;
    card.style.borderLeft = "4px solid " + getRiskColor(riskLevel);
  }

  /**
   * 渲染专业模式结果
   * @param {Object} result - 检测结果
   */
  function renderExpertResult(result) {
    elements.resultNormal.style.display = "none";
    elements.resultExpert.style.display = "block";

    const riskScore = result.risk_score || 0;

    // 风险评分
    elements.expertScoreValue.textContent = riskScore + "/100";
    elements.expertScoreValue.style.color = getRiskColor(result.risk_level);
    elements.expertProgressFill.style.width = Math.min(riskScore, 100) + "%";

    // 规则引擎
    const ruleEngine = result.rule_engine || {};
    if (ruleEngine.matched_rules && ruleEngine.matched_rules.length > 0) {
      let html = `<div class="detail-row"><span>规则评分：</span> ${ruleEngine.score || 0}</div>`;
      html += `<div class="detail-row"><span>匹配规则：</span></div>`;
      ruleEngine.matched_rules.forEach((rule) => {
        const ruleName = typeof rule === "object" ? (rule.rule || rule.detail || "") : String(rule);
        html += `<span class="detail-tag danger">${escapeHTML(ruleName)}</span>`;
      });
      elements.expertRuleContent.innerHTML = html;
    } else {
      elements.expertRuleContent.innerHTML =
        `<div class="detail-row"><span>规则评分：</span> ${ruleEngine.score || 0}</div>
         <div class="detail-row"><span>匹配规则：</span> 未匹配到危险规则</div>`;
    }

    // AI检测（综合概览）
    const aiDetection = result.ai_detection || {};
    if (aiDetection.model_loaded) {
      const hasInferenceResult = aiDetection.combined_confidence > 0;
      let aiHtml = "";
      if (hasInferenceResult) {
        aiHtml = `
          <div class="detail-row"><span>综合置信度：</span> ${formatPercent(aiDetection.combined_confidence)}</div>
          <div class="detail-row"><span>AI预测：</span>
            <span class="detail-tag ${aiDetection.prediction === 'phishing' ? 'danger' : 'safe'}">
              ${aiDetection.prediction === 'phishing' ? '钓鱼网站' : '正常网站'}
            </span>
          </div>
        `;
      } else {
        aiHtml = `
          <div class="detail-row"><span>状态：</span> <span style="color:#34a853;">模型已加载</span></div>
          <div class="detail-row"><span>说明：</span> 规则引擎已明确判定，未触发AI深度分析</div>
        `;
      }
      elements.expertAiContent.innerHTML = aiHtml;
    } else {
      elements.expertAiContent.innerHTML =
        `<div class="detail-row"><span>状态：</span> <span style="color:#ea4335;">AI模型未加载</span></div>`;
    }

    // URL CNN+BiLSTM 模型详情
    const urlCnn = result.url_cnn || {};
    if (urlCnn.model_loaded) {
      const hasInferenceResult = urlCnn.phishing_confidence > 0 || urlCnn.benign_confidence > 0;
      let urlCnnHtml = `
        <div class="detail-row"><span>模型：</span> Char-level CNN + Bi-LSTM</div>
        <div class="detail-row"><span>架构：</span> Embedding(128,32) → Conv1d(k=3,5,7) → BiLSTM(128) → FC(256)</div>
      `;
      if (hasInferenceResult) {
        urlCnnHtml += `
          <div class="detail-row"><span>钓鱼置信度：</span> ${formatPercent(urlCnn.phishing_confidence)}</div>
          <div class="detail-row"><span>正常置信度：</span> ${formatPercent(urlCnn.benign_confidence)}</div>
          <div class="detail-row"><span>预测结果：</span>
            <span class="detail-tag ${urlCnn.prediction === 'phishing' ? 'danger' : 'safe'}">
              ${urlCnn.prediction === 'phishing' ? '钓鱼网站' : '正常网站'}
            </span>
          </div>
        `;
        if (urlCnn.domain_trust_applied) {
          urlCnnHtml += `
            <div class="detail-row"><span>域名信任：</span> <span style="color:#34a853;">已应用（已知品牌域名，CNN置信度已调整）</span></div>
          `;
        }
      } else {
        urlCnnHtml += `
          <div class="detail-row"><span>状态：</span> <span style="color:#34a853;">已加载，未参与本次检测</span></div>
          <div class="detail-row"><span>说明：</span> 规则引擎已明确判定，无需CNN深度分析</div>
        `;
      }
      urlCnnHtml += `<div class="detail-row"><span>融合权重：</span> 0.40</div>`;
      elements.expertUrlCnnContent.innerHTML = urlCnnHtml;
    } else {
      elements.expertUrlCnnContent.innerHTML =
        `<div class="detail-row"><span>状态：</span> <span style="color:#ea4335;">模型未加载</span></div>
         <div class="detail-row"><span>说明：</span> 请训练模型并放置到后端models目录</div>`;
    }

    // 视觉CNN（已移除）

    // 表单分析
    const formAnalysis = result.form_analysis || {};
    if (formAnalysis.has_forms !== undefined) {
      elements.expertFormContent.innerHTML = `
        <div class="detail-row"><span>检测到表单：</span> ${formAnalysis.has_forms ? "是" : "否"}</div>
        <div class="detail-row"><span>密码字段数：</span> ${formAnalysis.password_fields || 0}</div>
        <div class="detail-row"><span>外部提交：</span> ${formAnalysis.external_action ? "是（危险）" : "否"}</div>
        <div class="detail-row"><span>表单评分：</span> ${formAnalysis.score || 0}</div>
      `;
    } else {
      elements.expertFormContent.innerHTML =
        `<div class="detail-row"><span>状态：</span> 暂无表单分析数据</div>`;
    }

    // 详细信息
    const details = result.details || [];
    if (Array.isArray(details) && details.length > 0) {
      let html = "";
      details.forEach((detail, index) => {
        html += `<div class="detail-row"><span>#${index + 1}：</span> ${escapeHTML(String(detail))}</div>`;
      });
      elements.expertDetailsContent.innerHTML = html;
    } else {
      elements.expertDetailsContent.innerHTML =
        `<div class="detail-row"><span>状态：</span> 暂无检测详情</div>`;
    }
  }

  // ============================================================
  // 模式切换
  // ============================================================

  /**
   * 切换显示模式
   * @param {string} mode - "normal" | "expert"
   */
  async function switchMode(mode) {
    state.currentMode = mode;
    await saveModeToStorage(mode);
    updateModeButtonText();

    // 如果有检测结果，重新渲染
    if (state.lastResult) {
      renderResult(state.lastResult);
    }
  }

  /**
   * 底部工具栏模式切换
   */
  async function toggleMode() {
    const newMode = state.currentMode === "normal" ? "expert" : "normal";
    await switchMode(newMode);
  }

  /**
   * 保存模式到storage
   */
  async function saveModeToStorage(mode) {
    try {
      await chrome.runtime.sendMessage({
        action: "save_settings",
        settings: {
          userMode: mode,
          realTimeEnabled: state.isRealTimeEnabled,
          backendUrl: state.backendUrl
        }
      });
    } catch (error) {
      console.warn("[弹窗] 保存模式失败:", error.message);
    }
  }

  /**
   * 更新模式切换按钮文字
   */
  function updateModeButtonText() {
    elements.btnModeText.textContent =
      state.currentMode === "normal" ? "专业模式" : "普通模式";
  }

  // ============================================================
  // 历史记录
  // ============================================================

  /**
   * 切换历史记录显示
   */
  async function toggleHistory() {
    if (elements.historySection.classList.contains("hidden")) {
      await loadHistory();
      elements.historySection.classList.remove("hidden");
    } else {
      elements.historySection.classList.add("hidden");
    }
  }

  /**
   * 加载并渲染检测历史
   */
  async function loadHistory() {
    try {
      const response = await chrome.runtime.sendMessage({
        action: "get_detection_history"
      });

      if (response.success && response.data && response.data.length > 0) {
        renderHistoryList(response.data);
      } else {
        elements.historyList.innerHTML =
          '<p class="history-empty">暂无检测记录</p>';
      }
    } catch (error) {
      elements.historyList.innerHTML =
        '<p class="history-empty">加载历史失败</p>';
    }
  }

  /**
   * 渲染历史列表
   */
  function renderHistoryList(history) {
    const recentHistory = history.slice(0, 20); // 最多显示20条
    let html = "";

    recentHistory.forEach((item) => {
      const result = item.result || {};
      const riskLevel = result.risk_level || "unknown";
      const badgeClass = getRiskBadgeClass(riskLevel);
      const levelText = getRiskLevelShortText(riskLevel);

      // 截断URL
      let urlDisplay = item.url || "";
      try {
        const urlObj = new URL(urlDisplay);
        urlDisplay = urlObj.hostname + urlObj.pathname;
      } catch (e) {}

      html += `
        <div class="history-item">
          <span class="history-item-icon">${getRiskIcon(riskLevel)}</span>
          <div class="history-item-info">
            <div class="history-item-url" title="${escapeHTML(item.url)}">${escapeHTML(urlDisplay)}</div>
            <div class="history-item-time">${formatTime(item.timestamp)}</div>
          </div>
          <span class="history-item-badge ${badgeClass}">${levelText}</span>
        </div>
      `;
    });

    elements.historyList.innerHTML = html;

    // 点击历史项可重新检测
    elements.historyList.querySelectorAll(".history-item").forEach((item, index) => {
      item.addEventListener("click", () => {
        const url = recentHistory[index].url;
        elements.urlInput.value = url;
        elements.historySection.classList.add("hidden");
        handleDetect();
      });
    });
  }

  /**
   * 清空检测历史
   */
  async function clearHistory() {
    try {
      await chrome.runtime.sendMessage({ action: "clear_history" });
      elements.historyList.innerHTML =
        '<p class="history-empty">暂无检测记录</p>';
    } catch (error) {
      console.warn("[弹窗] 清空历史失败:", error.message);
    }
  }

  // ============================================================
  // 设置页面
  // ============================================================

  /**
   * 打开设置页面
   */
  function openSettings() {
    chrome.tabs.create({ url: chrome.runtime.getURL("settings.html") });
  }

  // ============================================================
  // UI 工具函数
  // ============================================================

  /** 显示加载状态 */
  function showLoading() {
    elements.resultNormal.style.display = "none";
    elements.resultExpert.style.display = "none";
    elements.errorSection.classList.add("hidden");
    elements.loadingSection.classList.remove("hidden");
    elements.btnDetect.disabled = true;
    elements.btnLoadingSpinner.classList.remove("hidden");
  }

  /** 隐藏加载状态 */
  function hideLoading() {
    elements.loadingSection.classList.add("hidden");
    elements.btnDetect.disabled = false;
    elements.btnLoadingSpinner.classList.add("hidden");
  }

  /** 显示错误信息 */
  function showError(message) {
    elements.resultNormal.style.display = "none";
    elements.resultExpert.style.display = "none";
    elements.loadingSection.classList.add("hidden");
    elements.errorSection.classList.remove("hidden");
    elements.errorText.textContent = message;
    elements.btnDetect.disabled = false;
    elements.btnLoadingSpinner.classList.add("hidden");
  }

  /** 显示输入错误 */
  function showInputError(message) {
    elements.inputError.textContent = "⚠ " + message;
    elements.inputError.classList.remove("hidden");
  }

  /** 隐藏输入错误 */
  function hideInputError() {
    elements.inputError.classList.add("hidden");
  }

  // ============================================================
  // 格式化工具函数
  // ============================================================

  /**
   * 获取风险等级对应的CSS类名
   */
  function getRiskBadgeClass(level) {
    const map = {
      high: "danger",
      suspicious: "suspicious",
      low: "safe",
      safe: "safe",
      unknown: "unknown"
    };
    return map[level] || "unknown";
  }

  /**
   * 获取风险等级对应的颜色
   */
  function getRiskColor(level) {
    const map = {
      high: "#ea4335",
      suspicious: "#fbbc04",
      low: "#34a853",
      safe: "#34a853",
      unknown: "#9aa0a6"
    };
    return map[level] || "#9aa0a6";
  }

  /**
   * 获取风险等级图标
   */
  function getRiskIcon(level) {
    const map = {
      high: "🔴",
      suspicious: "🟡",
      low: "🟢",
      safe: "🟢",
      unknown: "⚪"
    };
    return map[level] || "⚪";
  }

  /**
   * 获取风险等级简短文字
   */
  function getRiskLevelShortText(level) {
    const map = {
      high: "高风险",
      suspicious: "可疑",
      low: "安全",
      safe: "安全",
      unknown: "未知"
    };
    return map[level] || "未知";
  }

  /**
   * 格式化百分比
   */
  function formatPercent(value) {
    if (value === null || value === undefined) return "--";
    return (parseFloat(value) * 100).toFixed(1) + "%";
  }

  /**
   * 格式化时间
   */
  function formatTime(timestamp) {
    if (!timestamp) return "--";
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diff = now - date;

      // 1分钟内
      if (diff < 60000) return "刚刚";
      // 1小时内
      if (diff < 3600000) return Math.floor(diff / 60000) + "分钟前";
      // 今天
      if (date.toDateString() === now.toDateString()) {
        return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
      }
      return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" }) +
        " " + date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    } catch (e) {
      return timestamp;
    }
  }

  /**
   * 验证URL格式
   */
  function isValidUrl(url) {
    try {
      const urlObj = new URL(url);
      return urlObj.protocol === "http:" || urlObj.protocol === "https:";
    } catch (e) {
      return false;
    }
  }

  /**
   * HTML转义
   */
  function escapeHTML(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(String(str)));
    return div.innerHTML;
  }

  // ============================================================
  // 启动
  // ============================================================

  init();
})();