/**
 * content.js - AI钓鱼检测系统内容脚本
 * 注入到每个页面，负责显示警告横幅和表单监控
 * 使用 Shadow DOM 隔离样式，不影响原页面
 */

(function () {
  "use strict";

  // ============================================================
  // 常量
  // ============================================================

  /** 扩展资源根路径 */
  const EXTENSION_URL = chrome.runtime.getURL("");

  /** Shadow DOM 容器ID */
  const CONTAINER_ID = "phishing-detector-container";

  // ============================================================
  // 初始化
  // ============================================================

  /**
   * 页面加载时初始化
   */
  function init() {
    // 设置表单监控
    setupFormMonitoring();

    console.log("[AI钓鱼检测] Content script 已注入:", window.location.href);
  }

  // ============================================================
  // 消息监听
  // ============================================================

  /**
   * 监听来自 background service worker 的消息
   */
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    try {
      switch (message.action) {
        case "show_warning_banner":
          showWarningBanner(message.data);
          sendResponse({ success: true });
          break;

        default:
          sendResponse({ success: false, error: "未知操作" });
      }
    } catch (error) {
      sendResponse({ success: false, error: error.message });
    }
    return false; // 不需要保持消息通道开放
  });

  // ============================================================
  // 警告横幅
  // ============================================================

  /**
   * 在页面顶部显示警告横幅
   * @param {Object} data - 包含 url, risk_score, risk_level, message
   */
  function showWarningBanner(data) {
    // 如果已有警告横幅，先移除
    removeWarningBanner();

    // 创建 Shadow DOM 宿主
    const host = document.createElement("div");
    host.id = CONTAINER_ID;
    host.style.cssText = "position:fixed;top:0;left:0;right:0;z-index:2147483647;";
    document.documentElement.appendChild(host);

    // 创建 Shadow DOM
    const shadow = host.attachShadow({ mode: "closed" });

    // 构建警告横幅HTML
    const bannerHTML = `
      <style>
        :host {
          all: initial;
        }
        .phishing-warning-banner {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 20px;
          background: linear-gradient(135deg, #fff3cd 0%, #fff8e1 100%);
          border-bottom: 3px solid #fbbc04;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                       "Helvetica Neue", Arial, sans-serif;
          font-size: 14px;
          color: #5d4037;
          box-shadow: 0 2px 8px rgba(0,0,0,0.15);
          animation: slideDown 0.3s ease-out;
        }
        @keyframes slideDown {
          from { transform: translateY(-100%); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .warning-content {
          display: flex;
          align-items: center;
          gap: 12px;
          flex: 1;
          min-width: 0;
        }
        .warning-icon {
          font-size: 24px;
          flex-shrink: 0;
          color: #f9a825;
        }
        .warning-text {
          flex: 1;
          min-width: 0;
        }
        .warning-title {
          font-weight: 700;
          font-size: 15px;
          color: #e65100;
          margin-bottom: 2px;
        }
        .warning-detail {
          font-size: 13px;
          color: #795548;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .warning-buttons {
          display: flex;
          gap: 8px;
          flex-shrink: 0;
          margin-left: 16px;
        }
        .btn-dismiss {
          padding: 6px 16px;
          border: 1px solid #ccc;
          border-radius: 6px;
          background: #fff;
          color: #555;
          cursor: pointer;
          font-size: 13px;
          font-weight: 500;
          transition: all 0.2s;
          white-space: nowrap;
        }
        .btn-dismiss:hover {
          background: #f5f5f5;
          border-color: #999;
        }
        .btn-detail {
          padding: 6px 16px;
          border: none;
          border-radius: 6px;
          background: #fbbc04;
          color: #fff;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          transition: all 0.2s;
          white-space: nowrap;
        }
        .btn-detail:hover {
          background: #f9a825;
          box-shadow: 0 2px 6px rgba(251,188,4,0.4);
        }
      </style>
      <div class="phishing-warning-banner">
        <div class="warning-content">
          <span class="warning-icon">⚠️</span>
          <div class="warning-text">
            <div class="warning-title">安全警告：此网站可能是钓鱼网站</div>
            <div class="warning-detail">
              ${escapeHTML(data.message || "该网站存在可疑特征，请谨慎操作")}
            </div>
          </div>
        </div>
        <div class="warning-buttons">
          <button class="btn-dismiss" id="btn-dismiss">忽略</button>
          <button class="btn-detail" id="btn-detail">查看详情</button>
        </div>
      </div>
    `;

    // 注入到 Shadow DOM
    shadow.innerHTML = bannerHTML;

    // 绑定按钮事件
    const dismissBtn = shadow.getElementById("btn-dismiss");
    const detailBtn = shadow.getElementById("btn-detail");

    dismissBtn.addEventListener("click", () => {
      removeWarningBanner();
    });

    detailBtn.addEventListener("click", () => {
      // 通过 popup 查看详情（发送消息给 background）
      chrome.runtime.sendMessage({
        action: "manual_detect",
        url: data.url || window.location.href
      });
      // 同时打开popup
      chrome.runtime.sendMessage({ action: "open_popup" });
    });
  }

  /**
   * 移除警告横幅
   */
  function removeWarningBanner() {
    const container = document.getElementById(CONTAINER_ID);
    if (container) {
      container.remove();
    }
  }

  // ============================================================
  // 表单监控
  // ============================================================

  /**
   * 设置表单提交监控
   * 检测密码表单提交到外部域名的情况
   */
  function setupFormMonitoring() {
    // 等待DOM加载完成
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", monitorForms);
    } else {
      monitorForms();
    }
  }

  /**
   * 监控页面中的表单
   */
  function monitorForms() {
    const forms = document.querySelectorAll("form");
    const currentHostname = window.location.hostname;

    forms.forEach((form) => {
      // 检查是否有密码字段
      const passwordFields = form.querySelectorAll(
        'input[type="password"], input[name*="password" i], ' +
        'input[name*="passwd" i], input[name*="pwd" i]'
      );

      if (passwordFields.length === 0) return;

      // 监听表单提交
      form.addEventListener("submit", function (event) {
        let formAction = form.action || form.getAttribute("action");

        if (formAction) {
          try {
            const actionUrl = new URL(formAction, window.location.href);
            // 如果提交到外部域名，发出警告
            if (actionUrl.hostname !== currentHostname &&
                actionUrl.hostname !== "" &&
                !actionUrl.hostname.endsWith("." + currentHostname)) {
              // 显示表单提交警告
              showFormSubmitWarning(event, actionUrl.hostname);
            }
          } catch (e) {
            // URL解析失败，忽略
          }
        }
      }, true); // 使用捕获阶段确保先于页面自身的事件处理
    });
  }

  /**
   * 当密码表单提交到外部域名时显示确认警告
   * @param {Event} event - 表单提交事件
   * @param {string} targetDomain - 目标域名
   */
  function showFormSubmitWarning(event, targetDomain) {
    const confirmed = confirm(
      `⚠️ 安全警告\n\n` +
      `您正在向外部域名 "${targetDomain}" 提交登录信息。\n` +
      `当前网站: ${window.location.hostname}\n\n` +
      `这可能是钓鱼攻击！请确认您信任该目标网站。\n\n` +
      `点击"确定"继续提交，点击"取消"停止提交。`
    );

    if (!confirmed) {
      event.preventDefault();
      event.stopImmediatePropagation();
      console.log("[AI钓鱼检测] 用户取消了向外部域名的表单提交");
    }
  }

  // ============================================================
  // 工具函数
  // ============================================================

  /**
   * HTML转义，防止XSS
   * @param {string} str - 原始字符串
   * @returns {string} 转义后的字符串
   */
  function escapeHTML(str) {
    const div = document.createElement("div");
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }

  // 启动
  init();
})();