/**
 * settings.js - AI钓鱼检测系统设置页面逻辑
 * 管理设置项的加载、保存、连接测试、历史显示
 */
(function () {
  "use strict";

  // ============================================================
  // 状态管理
  // ============================================================

  /** 当前设置状态 */
  const state = {
    userMode: "normal",
    isRealTimeEnabled: true,
    backendUrl: "http://127.0.0.1:5000",
    isBackendOnline: false
  };

  // ============================================================
  // DOM 元素引用
  // ============================================================

  const elements = {
    // 设置开关
    toggleExpertMode: document.getElementById("toggle-expert-mode"),
    toggleRealtime: document.getElementById("toggle-realtime"),
    inputBackendUrl: document.getElementById("input-backend-url"),

    // 连接状态
    statusDot: document.getElementById("status-dot"),
    statusText: document.getElementById("status-text"),
    statusDescription: document.getElementById("status-description"),

    // 模型状态
    urlCnnStatusDot: document.getElementById("url-cnn-status-dot"),
    urlCnnStatusText: document.getElementById("url-cnn-status-text"),

    // 按钮
    btnTestConnection: document.getElementById("btn-test-connection"),
    btnSaveSettings: document.getElementById("btn-save-settings"),
    btnClearHistory: document.getElementById("btn-clear-history"),

    // 历史
    historyList: document.getElementById("history-list"),
    historyCount: document.getElementById("history-count")
  };

  // ============================================================
  // 初始化
  // ============================================================

  async function init() {
    // 加载设置
    await loadSettings();

    // 绑定事件
    bindEvents();

    // 检查后端连接
    await checkBackendConnection();

    // 检查模型状态
    await checkModelStatus();

    // 加载历史
    await loadHistory();
  }

  /**
   * 从chrome.storage加载设置
   */
  async function loadSettings() {
    try {
      const response = await chrome.runtime.sendMessage({
        action: "get_settings"
      });

      if (response.success && response.data) {
        const settings = response.data;
        state.userMode = settings.userMode || "normal";
        state.isRealTimeEnabled = settings.realTimeEnabled !== false;
        state.backendUrl = settings.backendUrl || "http://127.0.0.1:5000";

        // 更新UI
        elements.toggleExpertMode.checked = (state.userMode === "expert");
        elements.toggleRealtime.checked = state.isRealTimeEnabled;
        elements.inputBackendUrl.value = state.backendUrl;
      }
    } catch (error) {
      console.error("[设置] 加载设置失败:", error.message);
    }
  }

  /**
   * 保存设置到chrome.storage
   */
  async function saveSettings() {
    try {
      state.userMode = elements.toggleExpertMode.checked ? "expert" : "normal";
      state.isRealTimeEnabled = elements.toggleRealtime.checked;
      state.backendUrl = elements.inputBackendUrl.value.trim() || "http://127.0.0.1:5000";

      await chrome.runtime.sendMessage({
        action: "save_settings",
        settings: {
          userMode: state.userMode,
          realTimeEnabled: state.isRealTimeEnabled,
          backendUrl: state.backendUrl
        }
      });

      // 保存成功后更新输入框值
      elements.inputBackendUrl.value = state.backendUrl;

      showToast("✅ 设置已保存");
    } catch (error) {
      console.error("[设置] 保存设置失败:", error.message);
      showToast("❌ 保存失败: " + error.message);
    }
  }

  // ============================================================
  // 事件绑定
  // ============================================================

  function bindEvents() {
    // 保存设置
    elements.btnSaveSettings.addEventListener("click", saveSettings);

    // 测试连接
    elements.btnTestConnection.addEventListener("click", checkBackendConnection);

    // 清空历史
    elements.btnClearHistory.addEventListener("click", clearHistory);

    // 自动保存 - 开关变化时
    elements.toggleExpertMode.addEventListener("change", () => {
      // 使用防抖，等用户操作完再保存
      debounceSave();
    });

    elements.toggleRealtime.addEventListener("change", () => {
      debounceSave();
    });

    // 后端地址变化时保存
    elements.inputBackendUrl.addEventListener("change", () => {
      debounceSave();
    });
  }

  // ============================================================
  // 后端连接检查
  // ============================================================

  /**
   * 检查后端连接状态
   */
  async function checkBackendConnection() {
    // 更新UI为检查中
    updateConnectionUI("checking");

    try {
      const response = await chrome.runtime.sendMessage({
        action: "check_backend_health"
      });

      if (response.success && response.data) {
        state.isBackendOnline = response.data.healthy;
        updateConnectionUI(state.isBackendOnline ? "online" : "offline");
      } else {
        state.isBackendOnline = false;
        updateConnectionUI("offline");
      }
    } catch (error) {
      state.isBackendOnline = false;
      updateConnectionUI("offline");
      console.error("[设置] 连接检查失败:", error.message);
    }
  }

  /**
   * 更新连接状态UI
   * @param {string} status - "online" | "offline" | "checking"
   */
  function updateConnectionUI(status) {
    switch (status) {
      case "online":
        elements.statusDot.className = "status-dot online";
        elements.statusText.className = "status-text online";
        elements.statusText.textContent = "已连接";
        elements.statusDescription.textContent = "后端服务运行正常";
        break;

      case "offline":
        elements.statusDot.className = "status-dot offline";
        elements.statusText.className = "status-text offline";
        elements.statusText.textContent = "未连接";
        elements.statusDescription.textContent = "无法连接到后端服务，请检查服务是否启动";
        break;

      case "checking":
      default:
        elements.statusDot.className = "status-dot";
        elements.statusText.className = "status-text";
        elements.statusText.textContent = "检查中...";
        elements.statusDescription.textContent = "正在检测后端服务状态...";
        break;
    }
  }

  /**
   * 检查URL CNN+BiLSTM模型加载状态
   * 通过后端health接口的models字段判断模型是否已加载
   */
  async function checkModelStatus() {
    // 默认显示检测中
    elements.urlCnnStatusDot.className = "status-dot";
    elements.urlCnnStatusText.className = "status-text";
    elements.urlCnnStatusText.textContent = "检测中...";

    try {
      const settings = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: "get_settings" }, (response) => {
          resolve(response && response.success ? response.data : { backendUrl: "http://127.0.0.1:5000" });
        });
      });

      // 调用后端health接口获取模型状态
      const response = await fetch(`${settings.backendUrl}/api/health`, {
        method: "GET"
      });

      if (!response.ok) {
        throw new Error("API请求失败");
      }

      const result = await response.json();
      const models = result.models || {};

      if (models.url_cnn_loaded) {
        elements.urlCnnStatusDot.className = "status-dot online";
        elements.urlCnnStatusText.className = "status-text online";
        elements.urlCnnStatusText.textContent = "已加载";
      } else {
        elements.urlCnnStatusDot.className = "status-dot offline";
        elements.urlCnnStatusText.className = "status-text offline";
        elements.urlCnnStatusText.textContent = "未加载";
      }
    } catch (error) {
      elements.urlCnnStatusDot.className = "status-dot offline";
      elements.urlCnnStatusText.className = "status-text offline";
      elements.urlCnnStatusText.textContent = "无法检测";
    }
  }

  // ============================================================
  // 历史记录
  // ============================================================

  /**
   * 加载检测历史
   */
  async function loadHistory() {
    try {
      const response = await chrome.runtime.sendMessage({
        action: "get_detection_history"
      });

      if (response.success && response.data && response.data.length > 0) {
        renderHistory(response.data);
      } else {
        elements.historyList.innerHTML =
          '<p class="history-empty">暂无检测记录</p>';
        elements.historyCount.textContent = "共 0 条记录";
      }
    } catch (error) {
      elements.historyList.innerHTML =
        '<p class="history-empty">加载历史失败</p>';
      elements.historyCount.textContent = "共 0 条记录";
    }
  }

  /**
   * 渲染历史列表
   */
  function renderHistory(history) {
    const recentHistory = history.slice(0, 20); // 最多显示20条
    elements.historyCount.textContent = `共 ${recentHistory.length} 条记录`;

    let html = "";
    recentHistory.forEach((item) => {
      const result = item.result || {};
      const riskLevel = result.risk_level || "unknown";
      const badgeClass = getRiskBadgeClass(riskLevel);
      const levelText = getRiskLevelText(riskLevel);

      // 处理URL显示
      let urlDisplay = item.url || "";
      try {
        const urlObj = new URL(urlDisplay);
        urlDisplay = urlObj.hostname + urlObj.pathname;
      } catch (e) {}

      html += `
        <div class="history-item">
          <span class="history-icon">${getRiskIcon(riskLevel)}</span>
          <div class="history-info">
            <div class="history-url" title="${escapeHTML(item.url)}">${escapeHTML(urlDisplay)}</div>
            <div class="history-time">${formatTime(item.timestamp)}</div>
          </div>
          <span class="history-badge ${badgeClass}">${levelText}</span>
        </div>
      `;
    });

    elements.historyList.innerHTML = html;
  }

  /**
   * 清空检测历史
   */
  async function clearHistory() {
    if (!confirm("确定要清空所有检测历史记录吗？此操作不可撤销。")) {
      return;
    }

    try {
      await chrome.runtime.sendMessage({ action: "clear_history" });
      elements.historyList.innerHTML =
        '<p class="history-empty">暂无检测记录</p>';
      elements.historyCount.textContent = "共 0 条记录";
      showToast("✅ 历史已清空");
    } catch (error) {
      showToast("❌ 清空失败: " + error.message);
    }
  }

  // ============================================================
  // 工具函数
  // ============================================================

  /** 防抖保存定时器 */
  let debounceTimer = null;

  /**
   * 防抖保存设置（500ms延迟）
   */
  function debounceSave() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      saveSettings();
    }, 500);
  }

  /**
   * 显示Toast提示
   */
  function showToast(message) {
    // 移除已有的toast
    const existing = document.querySelector(".toast-message");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "toast-message";
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: #323232;
      color: #fff;
      padding: 10px 24px;
      border-radius: 20px;
      font-size: 13px;
      font-weight: 500;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      z-index: 9999;
      animation: toastIn 0.3s ease-out, toastOut 0.3s ease-out 2.5s forwards;
      pointer-events: none;
    `;

    // 添加动画样式
    const style = document.createElement("style");
    style.textContent = `
      @keyframes toastIn { from { opacity:0; transform:translateX(-50%) translateY(20px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }
      @keyframes toastOut { from { opacity:1; } to { opacity:0; } }
    `;
    document.head.appendChild(style);

    document.body.appendChild(toast);

    // 3秒后自动移除
    setTimeout(() => {
      toast.remove();
      style.remove();
    }, 3000);
  }

  /**
   * 获取风险等级CSS类名
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
   * 获取风险等级文字
   */
  function getRiskLevelText(level) {
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
  // 启动
  // ============================================================

  init();
})();