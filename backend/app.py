"""
AI钓鱼网站检测后端 - 服务入口
Flask 应用主入口，负责创建应用、注册路由、配置CORS和启动服务
"""

import sys
import os
import logging
from datetime import datetime

# 确保项目根目录在 Python 路径中
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

from backend.utils.config import Config
from backend.api.routes import api_blueprint, set_hybrid_detector, register_websocket_handlers
from backend.models.hybrid_model import HybridDetector
from backend.utils.middleware import setup_request_logging, register_error_handlers

# ==================== 日志配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger(__name__)


# ==================== 创建 Flask 应用 ====================

def create_app() -> Flask:
    """创建并配置 Flask 应用。

    Returns:
        Flask: 配置完成的 Flask 应用实例
    """
    app = Flask(__name__)

    # 基本配置
    # 生产环境请务必通过环境变量 SECRET_KEY 设置安全的密钥
    # 示例: export SECRET_KEY="your-secure-random-key-here"
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "phishing-detector-dev-secret-key-change-in-production")
    app.config["JSON_AS_ASCII"] = False  # 支持中文JSON输出
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 限制请求体 16MB

    # 配置 CORS（允许浏览器扩展跨域访问）
    # 注意：生产环境建议限制为具体的扩展 ID 或已知域名
    # 当前配置允许所有来源以支持开发测试
    # 生产部署时应设置具体的 origins 列表
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": "*",  # 开发环境允许所有来源，生产环境应限制
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
        supports_credentials=True,
    )

    # 注册 API 路由
    app.register_blueprint(api_blueprint)

    # 注册中间件
    setup_request_logging(app)
    register_error_handlers(app)

    logger.info("Flask 应用创建完成")
    return app


# ==================== 创建 SocketIO 实例 ====================

def create_socketio(app: Flask) -> SocketIO:
    """创建并配置 Flask-SocketIO 实例。

    Args:
        app: Flask 应用实例

    Returns:
        SocketIO: 配置完成的 SocketIO 实例
        
    注意：
        WebSocket CORS 配置允许所有来源以支持开发测试。
        生产环境应限制为具体的扩展 ID 或已知域名。
    """
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",  # 开发环境允许所有来源，生产环境应限制
        async_mode="threading",
        logger=False,
        engineio_logger=False,
    )

    # 注册 WebSocket 事件处理器
    register_websocket_handlers(socketio)

    logger.info("SocketIO 实例创建完成")
    return socketio


# ==================== 初始化 HybridDetector ====================

def init_detector(url_cnn_path: str = None) -> HybridDetector:
    """初始化混合检测器。

    支持通过环境变量或参数指定模型路径，
    默认使用 Config 中的路径。

    Args:
        url_cnn_path: URL CNN+BiLSTM 模型权重路径

    Returns:
        HybridDetector: 初始化完成的检测器
    """
    # 优先使用参数，其次使用环境变量，最后使用默认配置
    url_cnn_path = (
        url_cnn_path
        or os.environ.get("URL_CNN_MODEL_PATH")
        or Config.URL_CNN_MODEL_PATH
    )

    logger.info(f"正在初始化 HybridDetector...")
    logger.info(f"  URL CNN+BiLSTM 模型路径: {url_cnn_path}")

    detector = HybridDetector(url_cnn_model_path=url_cnn_path)

    # 注入到 routes 模块
    set_hybrid_detector(detector)

    logger.info("HybridDetector 初始化完成")
    return detector


# ==================== 服务启动 ====================

def print_startup_info():
    """打印服务启动信息"""
    print("=" * 60)
    print("  AI钓鱼网站动态识别及防护系统 - 后端服务")
    print("=" * 60)
    print(f"  服务地址: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}")
    print(f"  API 根路径: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}/api")
    print(f"  健康检查: http://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}/api/health")
    print(f"  WebSocket: ws://{Config.BACKEND_HOST}:{Config.BACKEND_PORT}/ws")
    print(f"  启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  调试模式: {Config.DEBUG}")
    print(f"  规则引擎阈值: 低={Config.RULE_LOW_RISK_THRESHOLD}, 高={Config.RULE_HIGH_RISK_THRESHOLD}")
    print("-" * 60)
    print("  可用接口:")
    print("    POST /api/detect        - 单条URL检测")
    print("    POST /api/detect-batch  - 批量URL检测")
    print("    GET  /api/health         - 健康检查（含系统指标）")
    print("    GET  /api/model/info     - 模型信息")
    print("    POST /api/model/reload   - 模型热更新")
    print("    WS   /ws                 - WebSocket 实时检测")
    print("=" * 60)


def main():
    """主入口：启动 Flask 开发服务器（HTTP模式）。"""
    app = create_app()

    # 初始化 SocketIO
    socketio = create_socketio(app)

    # 初始化检测器
    detector = init_detector()

    # 打印启动信息
    print_startup_info()

    # 启动 Flask 开发服务器
    logger.info("正在启动 HTTP 服务...")
    app.run(
        host=Config.BACKEND_HOST,
        port=Config.BACKEND_PORT,
        debug=Config.DEBUG,
        use_reloader=False,  # 避免 SocketIO 重载问题
    )


if __name__ == "__main__":
    main()