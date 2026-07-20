"""
AI钓鱼网站检测后端 - 无头浏览器页面内容提取模块
使用 Playwright 无头浏览器访问目标URL，提取DOM信息用于表单分析

安全配置:
    - Docker/容器环境：使用 --no-sandbox 参数（容器内必须）
    - 本地环境：保持沙箱启用（推荐安全配置）
    - 自动检测运行环境并调整参数
"""

import logging
import os
from datetime import datetime

from ..utils.config import Config

logger = logging.getLogger(__name__)


# 延迟导入 Playwright，避免未安装时导入失败
_sync_playwright = None


def _get_playwright():
    """懒加载 Playwright 模块"""
    global _sync_playwright
    if _sync_playwright is None:
        try:
            from playwright.sync_api import sync_playwright as sp
            _sync_playwright = sp
        except ImportError:
            logger.error(
                "Playwright 未安装，请执行: pip install playwright && playwright install chromium"
            )
            raise
    return _sync_playwright


def _is_container_environment() -> bool:
    """检测是否运行在容器环境中。
    
    容器环境中必须使用 --no-sandbox 参数，否则 Chromium 无法启动。
    
    Returns:
        bool: True 表示在容器中运行
    """
    # 检查常见的容器环境标识
    indicators = [
        os.path.exists("/.dockerenv"),           # Docker 环境标识文件
        os.path.exists("/proc/1/cgroup"),        # 容器进程组
        "KUBERNETES_SERVICE_HOST" in os.environ, # Kubernetes 环境
    ]
    
    # 检查 /.dockerenv 文件内容
    if os.path.exists("/.dockerenv"):
        return True
    
    # 检查 /proc/1/cgroup 是否包含容器标识
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            if "docker" in content or "kubepods" in content:
                return True
    except Exception:
        pass
    
    return any(indicators)


class Screenshotter:
    """无头浏览器页面内容提取器，基于 Playwright Chromium。

    支持上下文管理器协议，使用完毕后自动释放浏览器资源。

    用法:
        with Screenshotter() as s:
            page_info = s.get_page_content("https://example.com")
    """

    def __init__(self, timeout: int = None):
        """初始化提取器，启动Chromium无头浏览器。

        Args:
            timeout: 页面加载超时时间（秒），默认使用Config.PAGE_LOAD_TIMEOUT
        """
        self._timeout = (timeout or Config.PAGE_LOAD_TIMEOUT) * 1000
        self._browser = None
        self._playwright = None
        self._initialized = False

    def _init_browser(self):
        """启动浏览器实例"""
        if self._initialized:
            return
        try:
            sp = _get_playwright()
            self._playwright = sp().start()
            
            # 根据运行环境选择浏览器参数
            # 容器环境必须使用 --no-sandbox，本地环境保持沙箱启用
            if _is_container_environment():
                browser_args = [
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
                logger.info("检测到容器环境，使用 --no-sandbox 参数")
            else:
                browser_args = [
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ]
                logger.info("本地环境，保持沙箱启用")
            
            self._browser = self._playwright.chromium.launch(
                headless=True,
                args=browser_args,
            )
            self._initialized = True
            logger.info("Playwright Chromium 浏览器已启动")
        except Exception as e:
            logger.error(f"浏览器启动失败: {e}")
            raise

    # ==================== 页面内容提取 ====================

    def get_page_content(self, url: str) -> dict:
        """访问页面并提取HTML内容和DOM信息。

        收集页面的标题、meta标签、HTML源码和可见文本内容。

        Args:
            url: 目标URL

        Returns:
            dict: {
                "url": str,           # 访问的URL
                "title": str,         # 页面标题
                "html": str,          # 完整HTML源码
                "text_content": str,  # 可见文本内容
                "meta_tags": list,    # meta标签信息列表
                "final_url": str,     # 最终跳转后的URL
                "status_code": int,   # HTTP状态码
                "timestamp": str,     # 抓取时间戳
            }
            失败时返回 None
        """
        self._init_browser()
        if not self._browser:
            return None

        page = None
        try:
            page = self._browser.new_page()
            logger.info(f"正在获取页面内容: {url}")

            response = page.goto(url, timeout=self._timeout, wait_until="domcontentloaded")

            status_code = response.status if response else 0
            final_url = page.url

            # 提取页面标题
            title = page.title()

            # 提取完整HTML
            html = page.content()

            # 提取可见文本内容
            text_content = page.inner_text("body") if html else ""

            # 提取meta标签
            meta_tags = []
            try:
                meta_elements = page.query_selector_all("meta")
                for meta in meta_elements:
                    name = meta.get_attribute("name") or meta.get_attribute("property") or ""
                    content_attr = meta.get_attribute("content") or ""
                    meta_tags.append({"name": name, "content": content_attr})
            except Exception as e:
                logger.warning(f"提取meta标签失败: {e}")

            result = {
                "url": url,
                "title": title,
                "html": html,
                "text_content": text_content[:10000],  # 限制文本长度
                "meta_tags": meta_tags,
                "final_url": final_url,
                "status_code": status_code,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"页面内容获取成功: {url}, title='{title[:50]}'")
            return result

        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg:
                logger.warning(f"页面内容获取超时: {url}")
            else:
                logger.error(f"页面内容获取异常: {url} - {e}")
            return None

        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    # ==================== 资源管理 ====================

    def close(self):
        """关闭浏览器实例，释放资源"""
        if self._browser:
            try:
                self._browser.close()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.warning(f"关闭浏览器异常: {e}")
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self._initialized = False

    # ==================== 上下文管理器协议 ====================

    def __enter__(self):
        """进入上下文管理器，初始化浏览器。"""
        self._init_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器，自动关闭浏览器。"""
        self.close()
        return False  # 不抑制异常