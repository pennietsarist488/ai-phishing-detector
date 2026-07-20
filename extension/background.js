/**
 * background.js - AI钓鱼检测系统 Service Worker
 * 负责核心拦截逻辑、后端通信、检测历史管理
 * 使用 Manifest V3 Service Worker 规范
 */

// ============================================================
// 配置常量
// ============================================================

/** 后端检测API基础地址 */
const BACKEND_URL = "http://127.0.0.1:5000";

/** 拦截页面URL（扩展内部页面） */
const BLOCKED_PAGE_URL = chrome.runtime.getURL("blocked.html");

/** 后端请求超时时间（毫秒） */
const FETCH_TIMEOUT_MS = 5000;

/** 检测历史最大保留条数 */
const MAX_HISTORY_SIZE = 100;

/** 存储键名 */
const STORAGE_KEYS = {
  HISTORY: "detection_history",
  SETTINGS: "detection_settings",
  TEMP_WHITELIST: "temp_whitelist"
};

// ============================================================
// 初始化
// ============================================================

/**
 * 扩展安装/更新时初始化
 */
chrome.runtime.onInstalled.addListener(async () => {
  console.log("[AI钓鱼检测] 扩展已安装/更新");

  // 初始化默认设置
  const existingSettings = await chrome.storage.local.get(STORAGE_KEYS.SETTINGS);
  if (!existingSettings[STORAGE_KEYS.SETTINGS]) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.SETTINGS]: {
        userMode: "normal",          // "normal" | "expert"
        realTimeEnabled: true,       // 是否启用实时检测
        backendUrl: BACKEND_URL      // 后端服务地址
      }
    });
  }

  // 初始化空历史记录
  const existingHistory = await chrome.storage.local.get(STORAGE_KEYS.HISTORY);
  if (!existingHistory[STORAGE_KEYS.HISTORY]) {
    await chrome.storage.local.set({
      [STORAGE_KEYS.HISTORY]: []
    });
  }

  // 检查后端健康状态
  await checkBackendHealth();
});

/**
 * Service Worker 启动时检查后端状态
 */
(async function init() {
  console.log("[AI钓鱼检测] Service Worker 已启动");
  await checkBackendHealth();
})();

// ============================================================
// 后端通信
// ============================================================

/**
 * 检查后端服务健康状态
 * @returns {Promise<boolean>} 后端是否可达
 */
async function checkBackendHealth() {
  try {
    const settings = await getSettings();
    const response = await fetchWithTimeout(
      `${settings.backendUrl}/api/health`,
      { method: "GET" },
      3000
    );
    const healthy = response.ok;
    console.log(`[AI钓鱼检测] 后端健康检查: ${healthy ? "正常" : "异常"}`);
    return healthy;
  } catch (error) {
    console.warn("[AI钓鱼检测] 后端健康检查失败:", error.message);
    return false;
  }
}

/**
 * 调用后端检测API
 * @param {string} url - 待检测的URL
 * @returns {Promise<Object>} 检测结果（已标准化）
 */
async function detectUrl(url) {
  const settings = await getSettings();

  try {
    const response = await fetchWithTimeout(
      `${settings.backendUrl}/api/detect`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url })
      },
      FETCH_TIMEOUT_MS
    );

    if (!response.ok) {
      throw new Error(`后端返回状态码: ${response.status}`);
    }

    const result = await response.json();
    console.log("[AI钓鱼检测] 检测结果:", result);
    return normalizeResponse(result);
  } catch (error) {
    console.error("[AI钓鱼检测] 检测请求失败:", error.message);
    return {
      is_phishing: false,
      risk_level: "unknown",
      risk_score: 0,
      error: error.message,
      message: "后端服务不可达，已放行"
    };
  }
}

/**
 * 将后端API响应标准化为前端统一格式
 * @param {Object} result - 后端原始响应
 * @returns {Object} 标准化后的检测结果
 */
function normalizeResponse(result) {
  // 提取后端字段
  const ruleResult = result.rule_result || {};
  const urlCnnResult = result.url_cnn_result || {};
  const formAnalysis = result.form_analysis || {};

  // 构建规则引擎结果（前端格式）
  const ruleEngine = {
    score: ruleResult.rule_score || 0,
    matched_rules: (ruleResult.matched_rules || []).map(r => ({
      rule: r.rule || "",
      detail: r.detail || "",
      weight: r.weight || 0
    }))
  };

  // 构建AI检测结果（前端格式 - 综合概览）
  const urlCnnConfidence = urlCnnResult.phishing_confidence || 0;
  const urlCnnLoaded = result.url_cnn_loaded === true;
  const aiDetection = {
    combined_confidence: urlCnnConfidence,
    url_cnn_confidence: urlCnnConfidence,
    prediction: urlCnnLoaded ? (urlCnnConfidence > 0.5 ? "phishing" : "benign") : "unavailable",
    model_loaded: urlCnnLoaded
  };

  // 构建URL CNN+BiLSTM模型详情（前端格式）
  const urlCnn = {
    model_name: "Char-level CNN + Bi-LSTM",
    architecture: "Embedding(128,32) → Conv1d(k=3,5,7) → BiLSTM(128) → FC(256)",
    phishing_confidence: urlCnnConfidence,
    benign_confidence: urlCnnResult.benign_confidence || (1 - urlCnnConfidence),
    prediction: urlCnnResult.prediction || (urlCnnLoaded ? (urlCnnConfidence > 0.5 ? "phishing" : "benign") : "unknown"),
    model_loaded: urlCnnLoaded,
    fusion_weight: 0.4,
    domain_trust_applied: urlCnnResult.domain_trust_applied || false
  };

  // 构建表单分析结果（前端格式）
  const formResult = {
    has_forms: (formAnalysis.form_count || 0) > 0,
    password_fields: formAnalysis.has_sensitive_fields ? 1 : 0,
    external_action: formAnalysis.overall_form_suspicious || false,
    score: formAnalysis.has_sensitive_fields ? 50 : 0,
    has_sensitive_fields: formAnalysis.has_sensitive_fields || false,
    sensitive_field_types: formAnalysis.sensitive_field_types || []
  };

  // 构建详细信息列表
  const details = [];
  if (ruleEngine.matched_rules.length > 0) {
    ruleEngine.matched_rules.forEach(r => {
      if (r.detail) details.push(r.detail);
    });
  }
  if (formResult.has_sensitive_fields) {
    details.push("页面包含敏感字段: " + (formResult.sensitive_field_types || []).join(", "));
  }
  if (formResult.external_action) {
    details.push("表单提交到外部可疑域名");
  }

  return {
    url: result.url || url,
    is_phishing: result.is_phishing || false,
    risk_score: result.final_risk_score || 0,
    risk_level: result.risk_level || "low",
    message: result.recommendation || "",
    rule_engine: ruleEngine,
    ai_detection: aiDetection,
    url_cnn: urlCnn,
    form_analysis: formResult,
    details: details,
    detection_stages: result.detection_stages || [],
    timestamp: result.timestamp || new Date().toISOString()
  };
}

/**
 * 带超时的fetch请求
 * @param {string} url - 请求URL
 * @param {Object} options - fetch选项
 * @param {number} timeoutMs - 超时时间(毫秒)
 * @returns {Promise<Response>}
 */
async function fetchWithTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

// ============================================================
// 设置管理
// ============================================================

/**
 * 获取用户设置
 * @returns {Promise<Object>} 设置对象
 */
async function getSettings() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.SETTINGS);
  return data[STORAGE_KEYS.SETTINGS] || {
    userMode: "normal",
    realTimeEnabled: true,
    backendUrl: BACKEND_URL
  };
}

// ============================================================
// 导航拦截 - 实时检测
// ============================================================

/**
 * 监听页面导航事件，对每个导航进行钓鱼检测
 */
chrome.webNavigation.onBeforeNavigate.addListener(async (details) => {
  // 只处理主框架导航（不是iframe）
  if (details.frameId !== 0) return;

  // 排除浏览器内部页面
  const url = details.url;
  if (url.startsWith("chrome://") ||
      url.startsWith("chrome-extension://") ||
      url.startsWith("edge://") ||
      url.startsWith("about:") ||
      url.startsWith("devtools://")) {
    return;
  }

  // 检查是否启用实时检测
  const settings = await getSettings();
  if (!settings.realTimeEnabled) return;

  // 检查是否在临时白名单中
  const isWhitelisted = await isTempWhitelisted(url);
  if (isWhitelisted) {
    console.log("[AI钓鱼检测] URL在临时白名单中，放行:", url);
    // 从白名单移除（一次性放行）
    await removeTempWhitelist(url);
    return;
  }

  console.log("[AI钓鱼检测] 检测URL:", url);

  try {
    const result = await detectUrl(url);

    // 保存到历史记录
    await saveDetectionHistory({
      url: url,
      timestamp: new Date().toISOString(),
      result: result
    });

    // 根据风险等级处理
    if (result.is_phishing && result.risk_level === "high") {
      // 高风险 → 重定向到拦截页面
      const params = new URLSearchParams({
        url: encodeURIComponent(url),
        risk_score: result.risk_score || 0,
        risk_level: result.risk_level || "high",
        rule_engine: encodeURIComponent(JSON.stringify(result.rule_engine || {})),
        ai_detection: encodeURIComponent(JSON.stringify(result.ai_detection || {})),
        url_cnn: encodeURIComponent(JSON.stringify(result.url_cnn || {})),
        form_analysis: encodeURIComponent(JSON.stringify(result.form_analysis || {})),
        details: encodeURIComponent(JSON.stringify(result.details || [])),
        timestamp: new Date().toISOString()
      });

      const blockedUrl = `${BLOCKED_PAGE_URL}?${params.toString()}`;
      console.log("[AI钓鱼检测] 拦截高风险网站，重定向到:", blockedUrl);

      // 更新标签页URL为拦截页面
      chrome.tabs.update(details.tabId, { url: blockedUrl });
    } else if (result.risk_level === "suspicious") {
      // 可疑 → 发送警告消息给content script
      console.log("[AI钓鱼检测] 可疑网站，发送警告:", url);
      try {
        chrome.tabs.sendMessage(details.tabId, {
          action: "show_warning_banner",
          data: {
            url: url,
            risk_score: result.risk_score || 0,
            risk_level: "suspicious",
            message: result.message || "此网站可能是钓鱼网站，请谨慎操作"
          }
        });
      } catch (e) {
        // content script 可能尚未加载，忽略错误
        console.warn("[AI钓鱼检测] 无法发送警告消息:", e.message);
      }
    } else {
      // 低风险/安全 → 放行
      console.log("[AI钓鱼检测] 安全网站，放行:", url);
    }
  } catch (error) {
    // 检测过程出错，允许正常浏览（fallback机制）
    console.error("[AI钓鱼检测] 检测过程异常，放行:", error.message);
  }
});

// ============================================================
// 消息处理
// ============================================================

/**
 * 监听来自popup/content script的消息
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender, sendResponse);
  return true; // 保持消息通道开放以支持异步sendResponse
});

/**
 * 消息路由处理
 */
async function handleMessage(message, sender, sendResponse) {
  switch (message.action) {
    // 手动检测URL（来自popup）
    case "manual_detect":
      try {
        const result = await detectUrl(message.url);
        await saveDetectionHistory({
          url: message.url,
          timestamp: new Date().toISOString(),
          result: result
        });
        sendResponse({ success: true, data: result });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    // 获取检测历史
    case "get_detection_history":
      try {
        const history = await getDetectionHistory();
        sendResponse({ success: true, data: history });
      } catch (error) {
        sendResponse({ success: false, error: error.message, data: [] });
      }
      break;

    // 清空检测历史
    case "clear_history":
      try {
        await chrome.storage.local.set({ [STORAGE_KEYS.HISTORY]: [] });
        sendResponse({ success: true });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    // 临时白名单放行
    case "allow_once":
      try {
        await addTempWhitelist(message.url);
        sendResponse({ success: true });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    // 检查后端健康状态
    case "check_backend_health":
      try {
        const healthy = await checkBackendHealth();
        sendResponse({ success: true, data: { healthy } });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    // 获取设置
    case "get_settings":
      try {
        const settings = await getSettings();
        sendResponse({ success: true, data: settings });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    // 保存设置
    case "save_settings":
      try {
        await chrome.storage.local.set({
          [STORAGE_KEYS.SETTINGS]: message.settings
        });
        sendResponse({ success: true });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    default:
      sendResponse({ success: false, error: "未知操作" });
  }
}

// ============================================================
// 检测历史管理
// ============================================================

/**
 * 保存检测记录
 * @param {Object} record - 检测记录 {url, timestamp, result}
 */
async function saveDetectionHistory(record) {
  const data = await chrome.storage.local.get(STORAGE_KEYS.HISTORY);
  let history = data[STORAGE_KEYS.HISTORY] || [];

  // 添加到历史开头
  history.unshift(record);

  // 最多保留 MAX_HISTORY_SIZE 条
  if (history.length > MAX_HISTORY_SIZE) {
    history = history.slice(0, MAX_HISTORY_SIZE);
  }

  await chrome.storage.local.set({ [STORAGE_KEYS.HISTORY]: history });
}

/**
 * 获取检测历史
 * @returns {Promise<Array>} 历史记录数组
 */
async function getDetectionHistory() {
  const data = await chrome.storage.local.get(STORAGE_KEYS.HISTORY);
  return data[STORAGE_KEYS.HISTORY] || [];
}

// ============================================================
// 临时白名单管理
// ============================================================

/**
 * 添加URL到临时白名单（一次性放行）
 * @param {string} url - 要放行的URL
 */
async function addTempWhitelist(url) {
  const data = await chrome.storage.local.get(STORAGE_KEYS.TEMP_WHITELIST);
  const whitelist = data[STORAGE_KEYS.TEMP_WHITELIST] || [];
  whitelist.push(url);
  await chrome.storage.local.set({ [STORAGE_KEYS.TEMP_WHITELIST]: whitelist });
}

/**
 * 检查URL是否在临时白名单中
 * @param {string} url - 要检查的URL
 * @returns {Promise<boolean>}
 */
async function isTempWhitelisted(url) {
  const data = await chrome.storage.local.get(STORAGE_KEYS.TEMP_WHITELIST);
  const whitelist = data[STORAGE_KEYS.TEMP_WHITELIST] || [];
  return whitelist.includes(url);
}

/**
 * 从临时白名单移除URL
 * @param {string} url - 要移除的URL
 */
async function removeTempWhitelist(url) {
  const data = await chrome.storage.local.get(STORAGE_KEYS.TEMP_WHITELIST);
  let whitelist = data[STORAGE_KEYS.TEMP_WHITELIST] || [];
  whitelist = whitelist.filter(item => item !== url);
  await chrome.storage.local.set({ [STORAGE_KEYS.TEMP_WHITELIST]: whitelist });
}