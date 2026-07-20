"""
AI钓鱼网站检测后端 - 中间件模块
提供请求日志、API限流和统一错误响应格式
"""

import time
import logging
from functools import wraps
from collections import defaultdict
from datetime import datetime

from flask import request, jsonify

logger = logging.getLogger(__name__)


# ==================== 请求日志中间件 ====================

def setup_request_logging(app):
    """为 Flask 应用注册请求日志中间件。

    记录每个请求的方法、路径、耗时和响应状态码。

    Args:
        app: Flask 应用实例
    """

    @app.before_request
    def before_request():
        request._start_time = time.time()

    @app.after_request
    def after_request(response):
        elapsed = (time.time() - getattr(request, "_start_time", time.time())) * 1000
        logger.info(
            "[%s] %s %s → %d (%.1fms)",
            request.remote_addr or "-",
            request.method,
            request.path,
            response.status_code,
            elapsed,
        )
        return response


# ==================== API 限流 ====================

class RateLimiter:
    """简单的内存速率限制器，基于滑动窗口算法。

    用法:
        limiter = RateLimiter(max_requests=60, window_seconds=60)
        @limiter.limit
        def my_view():
            ...
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._clients = defaultdict(list)

    def _cleanup(self, client_ip: str, now: float):
        """清理过期的请求记录。"""
        window_start = now - self._window_seconds
        self._clients[client_ip] = [
            t for t in self._clients[client_ip] if t > window_start
        ]

    def is_allowed(self, client_ip: str) -> bool:
        """检查客户端是否在限流允许范围内。"""
        now = time.time()
        self._cleanup(client_ip, now)
        if len(self._clients[client_ip]) >= self._max_requests:
            return False
        self._clients[client_ip].append(now)
        return True

    def limit(self, f):
        """限流装饰器。"""

        @wraps(f)
        def decorated(*args, **kwargs):
            client_ip = request.remote_addr or "127.0.0.1"
            if not self.is_allowed(client_ip):
                return jsonify({
                    "error": "请求过于频繁",
                    "message": f"每分钟最多 {self._max_requests} 次请求，请稍后再试",
                    "retry_after_seconds": self._window_seconds,
                }), 429
            return f(*args, **kwargs)

        return decorated


# 全局限流器实例
detect_limiter = RateLimiter(max_requests=60, window_seconds=60)
batch_limiter = RateLimiter(max_requests=10, window_seconds=60)


# ==================== 统一错误响应 ====================

def error_response(message: str, status_code: int = 400, **extra):
    """生成统一的错误响应JSON。

    Args:
        message: 错误描述
        status_code: HTTP状态码
        **extra: 额外的响应字段

    Returns:
        (Flask Response, int): JSON响应体和状态码
    """
    body = {
        "error": _status_message(status_code),
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    body.update(extra)
    return jsonify(body), status_code


def _status_message(code: int) -> str:
    return {
        400: "请求参数错误",
        401: "未授权",
        403: "禁止访问",
        404: "资源不存在",
        429: "请求过于频繁",
        500: "服务器内部错误",
    }.get(code, "未知错误")


def register_error_handlers(app):
    """为 Flask 应用注册全局错误处理器。"""

    @app.errorhandler(400)
    def bad_request(e):
        return error_response(str(e) or "请求参数错误", 400)

    @app.errorhandler(404)
    def not_found(e):
        return error_response("请求的资源不存在", 404)

    @app.errorhandler(405)
    def method_not_allowed(e):
        return error_response("不支持的请求方法", 405)

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("未捕获的服务器错误")
        return error_response("服务器内部错误，请稍后再试", 500)