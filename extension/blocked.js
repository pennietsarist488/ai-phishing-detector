/**
 * blocked.js - AI钓鱼检测系统拦截页面逻辑
 * 解析URL参数中的检测结果，渲染风险信息，处理用户操作
 */
(function () {
  "use strict";

  // ============================================================
  // DOM 元素引用
  // ============================================================

  const elements = {
    blockedUrlText: document.getElementById("blocked-url-text"),
    riskLevel: document.getElementById("risk-level"),
    riskScore: document.getElementById("risk-score"),
    riskScoreBar: document.getElementById("risk-score-bar"),
    detectTime: document.getElementById("detect-time"),
    btnGoBack: document.getElementById("btn-go-back"),
    btnContinue: document.getElementById("btn-continue"),
    btnToggleDetail: document.getElementById("btn-toggle-detail"),
    detailContent: document.getElementById("detail-content"),
    ruleEngineDetail: document.getElementById("rule-engine-detail"),
    aiDetectionDetail: document.getElementById("ai-detection-detail"),
    urlCnnDetail: document.getElementById("url-cnn-detail"),
    formAnalysisDetail: document.getElementById("form-analysis-detail"),
    detailsList: document.getElementById("details-list")
  };

  // ============================================================
  // 数据解析
  // ============================================================

  /**
   * 从URL参数解析检测结果数据
   * @returns {Object} 解析后的检测数据
   */
  function parseUrlParams() {
    const params = new URLSearchParams(window.location.search);
    const data = {
      url: "",
      riskScore: 0,
      riskLevel: "high",
      ruleEngine: null,
      aiDetection: null,
      urlCnn: null,
      formAnalysis: null,
      details: [],
      timestamp: ""
    };

    try {
      data.url = decodeURIComponent(params.get("url") || "");
      data.riskScore = parseInt(params.get("risk_score") || "0", 10);
      data.riskLevel = params.get("risk_level") || "high";
      data.timestamp = params.get("timestamp") || new Date().toISOString();

      // 解析JSON字段（安全解码）
      const ruleEngineStr = params.get("rule_engine");
      if (ruleEngineStr) {
        data.ruleEngine = safeJSONParse(decodeURIComponent(ruleEngineStr));
      }

      const aiDetectionStr = params.get("ai_detection");
      if (aiDetectionStr) {
        data.aiDetection = safeJSONParse(decodeURIComponent(aiDetectionStr));
      }

      const urlCnnStr = params.get("url_cnn");
      if (urlCnnStr) {
        data.urlCnn = safeJSONParse(decodeURIComponent(urlCnnStr));
      }

      const formAnalysisStr = params.get("form_analysis");
      if (formAnalysisStr) {
        data.formAnalysis = safeJSONParse(decodeURIComponent(formAnalysisStr));
      }

      const detailsStr = params.get("details");
      if (detailsStr) {
        data.details = safeJSONParse(decodeURIComponent(detailsStr));
      }
    } catch (error) {
      console.error("[拦截页面] URL参数解析失败:", error.message);
    }

    return data;
  }

  /**
   * 安全JSON解析
   * @param {string} str - JSON字符串
   * @returns {*} 解析结果，失败返回null
   */
  function safeJSONParse(str) {
    try {
      return JSON.parse(str);
    } catch (e) {
      return null;
    }
  }

  // ============================================================
  // 页面渲染
  // ============================================================

  /**
   * 渲染风险信息
   * @param {Object} data - 检测数据
   */
  function renderRiskInfo(data) {
    // 被拦截URL
    elements.blockedUrlText.textContent = data.url || "未知网站";

    // 风险等级
    elements.riskLevel.textContent = getRiskLevelText(data.riskLevel);
    elements.riskLevel.className = "detail-tag " + getRiskTagClass(data.riskLevel);

    // 风险评分
    elements.riskScore.textContent = data.riskScore + "/100";
    elements.riskScoreBar.style.width = Math.min(data.riskScore, 100) + "%";

    // 检测时间
    elements.detectTime.textContent = formatTime(data.timestamp);
  }

  /**
   * 渲染详细报告
   * @param {Object} data - 检测数据
   */
  function renderDetailReport(data) {
    // 规则引擎结果
    renderRuleEngine(data.ruleEngine);

    // AI检测结果（综合概览）
    renderAiDetection(data.aiDetection);

    // URL CNN+BiLSTM模型详情
    renderUrlCnn(data.urlCnn || data.aiDetection);

    // 表单分析结果
    renderFormAnalysis(data.formAnalysis);

    // 详细信息列表
    renderDetails(data.details);
  }

  /**
   * 渲染规则引擎结果
   */
  function renderRuleEngine(ruleEngine) {
    if (!ruleEngine) {
      elements.ruleEngineDetail.innerHTML =
        '<div class="detail-row"><span>状态：</span> 暂无数据</div>';
      return;
    }

    let html = "";
    html += `<div class="detail-row"><span>规则评分：</span> ${ruleEngine.score || 0}</div>`;

    if (ruleEngine.matched_rules && ruleEngine.matched_rules.length > 0) {
      html += `<div class="detail-row"><span>匹配规则：</span></div>`;
      ruleEngine.matched_rules.forEach((rule) => {
        const ruleName = typeof rule === "object" ? (rule.rule || rule.detail || "") : String(rule);
        html += `<div style="padding-left:16px;padding-bottom:2px;">
          <span class="detail-tag danger">${escapeHTML(ruleName)}</span>
        </div>`;
      });
    } else {
      html += `<div class="detail-row"><span>匹配规则：</span> 未匹配到危险规则</div>`;
    }

    elements.ruleEngineDetail.innerHTML = html;
  }

  /**
   * 渲染AI检测结果（综合概览）
   */
  function renderAiDetection(aiDetection) {
    if (!aiDetection || !aiDetection.model_loaded) {
      elements.aiDetectionDetail.innerHTML =
        '<div class="detail-row"><span>状态：</span> <span style="color:#ea4335;">AI模型未加载</span></div>';
      return;
    }

    const hasInferenceResult = aiDetection.combined_confidence > 0;
    let html = "";

    if (hasInferenceResult) {
      html += `<div class="detail-row">
        <span>综合置信度：</span> ${formatPercent(aiDetection.combined_confidence)}
      </div>`;
      if (aiDetection.prediction) {
        html += `<div class="detail-row">
          <span>AI预测：</span>
          <span class="detail-tag ${aiDetection.prediction === 'phishing' ? 'danger' : 'safe'}">
            ${aiDetection.prediction === 'phishing' ? '钓鱼网站' : '正常网站'}
          </span>
        </div>`;
      }
    } else {
      html += `<div class="detail-row">
        <span>状态：</span> <span style="color:#34a853;">模型已加载</span>
      </div>`;
      html += `<div class="detail-row">
        <span>说明：</span> 规则引擎已明确判定，未触发AI深度分析
      </div>`;
    }

    elements.aiDetectionDetail.innerHTML = html;
  }

  /**
   * 渲染URL CNN+BiLSTM模型详情
   */
  function renderUrlCnn(urlCnn) {
    if (!urlCnn || !urlCnn.model_loaded) {
      elements.urlCnnDetail.innerHTML =
        '<div class="detail-row"><span>状态：</span> <span style="color:#ea4335;">模型未加载</span></div>' +
        '<div class="detail-row"><span>说明：</span> 请训练模型并放置到后端models目录</div>';
      return;
    }

    const hasInferenceResult = urlCnn.phishing_confidence > 0 || urlCnn.benign_confidence > 0;
    let html = "";
    html += `<div class="detail-row">
      <span>模型：</span> ${urlCnn.model_name || "Char-level CNN + Bi-LSTM"}
    </div>`;
    html += `<div class="detail-row">
      <span>架构：</span> ${urlCnn.architecture || "Embedding(128,32) → Conv1d(k=3,5,7) → BiLSTM(128) → FC(256)"}
    </div>`;

    if (hasInferenceResult) {
      html += `<div class="detail-row">
        <span>钓鱼置信度：</span> ${formatPercent(urlCnn.phishing_confidence)}
      </div>`;
      html += `<div class="detail-row">
        <span>正常置信度：</span> ${formatPercent(urlCnn.benign_confidence)}
      </div>`;
      html += `<div class="detail-row">
        <span>预测结果：</span>
        <span class="detail-tag ${urlCnn.prediction === 'phishing' ? 'danger' : 'safe'}">
          ${urlCnn.prediction === 'phishing' ? '钓鱼网站' : '正常网站'}
        </span>
      </div>`;
      if (urlCnn.domain_trust_applied) {
        html += `<div class="detail-row">
          <span>域名信任：</span> <span style="color:#34a853;">已应用（已知品牌域名，CNN置信度已调整）</span>
        </div>`;
      }
    } else {
      html += `<div class="detail-row">
        <span>状态：</span> <span style="color:#34a853;">已加载，未参与本次检测</span>
      </div>`;
      html += `<div class="detail-row">
        <span>说明：</span> 规则引擎已明确判定，无需CNN深度分析
      </div>`;
    }

    html += `<div class="detail-row">
      <span>融合权重：</span> ${urlCnn.fusion_weight || 0.4}
    </div>`;

    elements.urlCnnDetail.innerHTML = html;
  }

  /**
   * 渲染表单分析结果
   */
  function renderFormAnalysis(formAnalysis) {
    if (!formAnalysis) {
      elements.formAnalysisDetail.innerHTML =
        '<div class="detail-row"><span>状态：</span> 暂无数据</div>';
      return;
    }

    let html = "";
    html += `<div class="detail-row">
      <span>检测到表单：</span> ${formAnalysis.has_forms ? "是" : "否"}
    </div>`;
    html += `<div class="detail-row">
      <span>密码字段数：</span> ${formAnalysis.password_fields || 0}
    </div>`;
    html += `<div class="detail-row">
      <span>外部提交：</span> ${formAnalysis.external_action ? "是（危险）" : "否"}
    </div>`;
    html += `<div class="detail-row">
      <span>表单评分：</span> ${formAnalysis.score || 0}
    </div>`;

    elements.formAnalysisDetail.innerHTML = html;
  }

  /**
   * 渲染详细信息列表
   */
  function renderDetails(details) {
    if (!details || !Array.isArray(details) || details.length === 0) {
      elements.detailsList.innerHTML =
        '<div class="detail-row"><span>状态：</span> 暂无检测详情</div>';
      return;
    }

    let html = "";
    details.forEach((detail, index) => {
      html += `<div class="detail-row">
        <span>#${index + 1}：</span> ${escapeHTML(String(detail))}
      </div>`;
    });

    elements.detailsList.innerHTML = html;
  }

  // ============================================================
  // 按钮事件处理
  // ============================================================

  /**
   * 返回安全页面
   */
  function goBack() {
    // 尝试返回上一页
    if (window.history.length > 1) {
      window.history.back();
    } else {
      // 无法返回时关闭标签页
      try {
        chrome.runtime.sendMessage({ action: "close_tab" });
      } catch (e) {
        window.close();
      }
    }
  }

  /**
   * 继续访问（临时放行）
   */
  async function continueToSite() {
    const data = parseUrlParams();

    if (!data.url) {
      alert("无法获取目标URL");
      return;
    }

    try {
      // 发送临时白名单请求
      await chrome.runtime.sendMessage({
        action: "allow_once",
        url: data.url
      });

      // 跳转到目标网站
      window.location.href = data.url;
    } catch (error) {
      console.error("[拦截页面] 放行失败:", error.message);
      // 降级：直接跳转
      window.location.href = data.url;
    }
  }

  /**
   * 切换详细报告显示
   */
  function toggleDetail() {
    const content = elements.detailContent;
    const btn = elements.btnToggleDetail;

    if (content.classList.contains("open")) {
      content.classList.remove("open");
      btn.innerHTML = "📊 查看详细报告 ▼";
    } else {
      content.classList.add("open");
      btn.innerHTML = "📊 收起详细报告 ▲";
    }
  }

  // ============================================================
  // 工具函数
  // ============================================================

  /**
   * 获取风险等级显示文字
   */
  function getRiskLevelText(level) {
    const map = {
      high: "🔴 高风险",
      suspicious: "🟡 可疑",
      low: "🟢 低风险",
      safe: "🟢 安全",
      unknown: "⚪ 未知"
    };
    return map[level] || "🔴 高风险";
  }

  /**
   * 获取风险标签CSS类
   */
  function getRiskTagClass(level) {
    const map = {
      high: "danger",
      suspicious: "warning",
      low: "safe",
      safe: "safe",
      unknown: ""
    };
    return map[level] || "danger";
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
      return date.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      });
    } catch (e) {
      return timestamp;
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
  // 初始化
  // ============================================================

  function init() {
    const data = parseUrlParams();

    // 渲染风险信息
    renderRiskInfo(data);

    // 预渲染详细报告（折叠时已准备就绪）
    renderDetailReport(data);

    // 绑定事件
    elements.btnGoBack.addEventListener("click", goBack);
    elements.btnContinue.addEventListener("click", continueToSite);
    elements.btnToggleDetail.addEventListener("click", toggleDetail);

    console.log("[拦截页面] 已初始化，拦截URL:", data.url);
  }

  // 启动
  init();
})();