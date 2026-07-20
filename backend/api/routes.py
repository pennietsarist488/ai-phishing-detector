"""
AI钓鱼网站检测后端 - API 路由模块
提供 RESTful API 和 WebSocket 事件处理

API 文档
========
基础路径: /api

健康检查:
    GET /api/health
    返回: {"status": "ok", "timestamp": "...", "models": {"url_cnn_loaded": true}}

单条检测:
    POST /api/detect
    请求: {"url": "https://..."}
    返回: 完整检测结果（规则引擎、CNN、融合评分）

批量检测:
    POST /api/detect-batch
    请求: {"urls": ["https://...", ...]}
    返回: {"results": [...], "total": int, "summary": {...}}

模型管理:
    POST /api/model/reload
    返回: {"status": "ok", "url_cnn_reloaded": true}

WebSocket事件:
    detect_url: 发送 {"url": "..."} 进行实时检测
    detect_result: 接收检测结果
"""

import logging
import time
import os
import traceback
from datetime import datetime

from flask import Blueprint, request, jsonify
from flask_socketio import emit

from ..utils.config import Config
from ..utils.url_utils import is_valid_url, normalize_url
from ..utils.middleware import detect_limiter, batch_limiter

logger = logging.getLogger(__name__)

# 创建 Blueprint
api_blueprint = Blueprint("api", __name__, url_prefix="/api")

# 延迟导入 HybridDetector，避免循环依赖
_hybrid_detector = None


def get_hybrid_detector():
    """获取全局 HybridDetector 实例（延迟初始化引用）。"""
    global _hybrid_detector
    if _hybrid_detector is None:
        from ..models.hybrid_model import HybridDetector
        _hybrid_detector = HybridDetector()
    return _hybrid_detector


def set_hybrid_detector(detector):
    """设置全局 HybridDetector 实例（由 app.py 在启动时调用）。"""
    global _hybrid_detector
    _hybrid_detector = detector


# ==================== RESTful API 路由 ====================

@api_blueprint.route("/health", methods=["GET"])
def health_check():
    """增强的健康检查接口。

    返回服务状态、模型加载情况、系统资源使用等指标。

    返回:
        JSON: {
            "status": "ok",
            "timestamp": "...",
            "models": {...},
            "system": {...}
        }
    """
    detector = get_hybrid_detector()

    # 收集系统指标
    system_info = {}
    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        system_info = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_rss_mb": round(memory_info.rss / 1024 / 1024, 2),
            "memory_percent": round(process.memory_percent(), 2),
            "threads": process.num_threads(),
        }
    except ImportError:
        system_info = {"note": "psutil 未安装，系统指标不可用"}

    # 模型推理延迟基准测试
    inference_latency = None
    if detector.url_cnn_loaded:
        try:
            start = time.time()
            detector.url_cnn.predict("https://www.google.com")
            inference_latency = round((time.time() - start) * 1000, 2)
        except Exception:
            inference_latency = None

    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "service": "AI钓鱼网站检测后端",
        "version": "1.0.0",
        "models": {
            "url_cnn_loaded": detector.url_cnn_loaded,
            "inference_latency_ms": inference_latency,
        },
        "system": system_info,
    })


@api_blueprint.route("/detect", methods=["POST"])
@detect_limiter.limit
def detect_url():
    """单条URL检测接口。

    接收JSON: {"url": "https://..."}

    检测流程:
        1. 验证URL有效性
        2. 调用混合检测器进行完整检测（规则引擎+CNN+表单分析）

    返回:
        JSON: 完整的检测结果字典
    """
    try:
        data = request.get_json(silent=True)
        if not data or "url" not in data:
            return jsonify({
                "error": "请求参数缺失",
                "message": "请提供 {'url': '...'} 格式的JSON数据",
            }), 400

        url = data.get("url", "").strip()
        if not url:
            return jsonify({
                "error": "URL为空",
                "message": "请提供有效的URL地址",
            }), 400

        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        if not is_valid_url(url):
            return jsonify({
                "error": "无效的URL",
                "message": f"提供的URL格式不正确: {url}",
                "url": url,
            }), 400

        normalized_url = normalize_url(url)
        logger.info(f"收到检测请求: {url}")

        detector = get_hybrid_detector()
        result = detector.detect(url=normalized_url)
        return jsonify(result), 200

    except Exception as e:
        logger.error(f"检测接口异常: {e}\n{traceback.format_exc()}")
        # 生产环境返回通用错误消息，避免暴露内部信息
        return jsonify({
            "error": "服务器内部错误",
            "message": "检测过程中发生错误，请稍后再试",
            "timestamp": datetime.now().isoformat(),
        }), 500


@api_blueprint.route("/detect-batch", methods=["POST"])
@batch_limiter.limit
def detect_batch():
    """批量URL检测接口。

    接收JSON: {"urls": ["https://...", "https://..."]}

    每个URL均执行完整的混合检测（规则引擎+CNN模型）。

    返回:
        JSON: {"results": [...], "total": int, "summary": {...}}
    """
    try:
        data = request.get_json(silent=True)
        if not data or "urls" not in data:
            return jsonify({
                "error": "请求参数缺失",
                "message": "请提供 {'urls': [...]} 格式的JSON数据",
            }), 400

        urls = data.get("urls", [])
        if not isinstance(urls, list) or len(urls) == 0:
            return jsonify({
                "error": "URL列表为空",
                "message": "请提供至少一个URL地址",
            }), 400

        max_batch = 20
        if len(urls) > max_batch:
            return jsonify({
                "error": "批量数量超限",
                "message": f"单次批量检测最多支持{max_batch}条URL",
            }), 400

        detector = get_hybrid_detector()
        results = []
        phishing_count = 0
        suspicious_count = 0
        benign_count = 0

        for url in urls:
            url = url.strip()
            if not url:
                continue

            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            if not is_valid_url(url):
                results.append({
                    "url": url,
                    "error": "无效URL",
                    "is_valid_url": False,
                })
                continue

            normalized_url = normalize_url(url)

            try:
                result = detector.detect(url=normalized_url)
                risk_level = result.get("risk_level", "low")

                if risk_level == "high":
                    phishing_count += 1
                elif risk_level == "suspicious":
                    suspicious_count += 1
                else:
                    benign_count += 1

                results.append({
                    "url": normalized_url,
                    "final_risk_score": result.get("final_risk_score", 0),
                    "risk_level": risk_level,
                    "is_phishing": result.get("is_phishing", False),
                    "rule_score": result.get("rule_result", {}).get("rule_score", 0),
                    "url_cnn_confidence": result.get("url_cnn_result", {}).get("phishing_confidence", 0) if result.get("url_cnn_result") else 0,
                    "matched_rules": [
                        {"rule": r["rule"], "detail": r["detail"]}
                        for r in result.get("rule_result", {}).get("matched_rules", [])
                    ],
                })
            except Exception as e:
                logger.error(f"批量检测URL异常: {url} - {e}")
                results.append({
                    "url": url,
                    "error": str(e),
                })

        return jsonify({
            "results": results,
            "total": len(results),
            "summary": {
                "phishing": phishing_count,
                "suspicious": suspicious_count,
                "benign": benign_count,
                "error": len(urls) - len(results),
            },
            "timestamp": datetime.now().isoformat(),
        }), 200

    except Exception as e:
        logger.error(f"批量检测接口异常: {e}\n{traceback.format_exc()}")
        # 生产环境返回通用错误消息，避免暴露内部信息
        return jsonify({
            "error": "服务器内部错误",
            "message": "批量检测过程中发生错误，请稍后再试",
        }), 500


# ==================== 模型管理 ====================

@api_blueprint.route("/model/reload", methods=["POST"])
def reload_model():
    """模型热更新接口。

    在不重启服务的情况下重新加载模型文件。
    支持文件监控场景：训练脚本生成新模型后，调用此接口即可生效。
    
    安全限制：
        - 仅允许本地管理员访问（127.0.0.1）
        - 生产环境应添加 API Token 认证

    返回:
        JSON: {"status": "ok", "url_cnn_reloaded": true}
    """
    # 安全检查：仅允许本地管理员访问
    client_ip = request.remote_addr or "unknown"
    allowed_ips = ["127.0.0.1", "::1", "localhost"]
    if client_ip not in allowed_ips:
        logger.warning(f"拒绝远程模型重载请求: IP={client_ip}")
        return jsonify({
            "error": "权限拒绝",
            "message": "此接口仅允许本地管理员访问",
        }), 403
    
    detector = get_hybrid_detector()
    previous_state = detector.url_cnn_loaded

    try:
        detector.reload_model()
        logger.info(f"模型热更新执行: IP={client_ip}, 结果={detector.url_cnn_loaded}")
        return jsonify({
            "status": "ok",
            "url_cnn_reloaded": detector.url_cnn_loaded,
            "previous_state": previous_state,
            "message": "模型已重新加载" if detector.url_cnn_loaded else "模型加载失败，请检查模型文件",
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"模型热更新失败: {e}")
        return jsonify({
            "error": "模型热更新失败",
            "message": "服务器内部错误，请查看日志",
            "timestamp": datetime.now().isoformat(),
        }), 500


@api_blueprint.route("/model/info", methods=["GET"])
def model_info():
    """获取模型详细信息。

    返回:
        JSON: 模型架构、路径、加载状态等
    """
    detector = get_hybrid_detector()
    return jsonify({
        "status": "ok",
        "model_info": {
            "url_cnn": {
                "loaded": detector.url_cnn_loaded,
                "model_path": Config.URL_CNN_MODEL_PATH,
                "architecture": "Embedding(128,32) → Conv1d(k=3,5,7) → BiLSTM(128) → FC(256)",
                "url_max_len": Config.URL_MAX_LEN,
                "inference_timeout_s": detector.CNN_INFERENCE_TIMEOUT,
            },
        },
        "fusion_weights": {
            "rule_engine": Config.RULE_WEIGHT,
            "url_cnn": Config.URL_CNN_WEIGHT,
            "form_analysis": Config.FORM_WEIGHT,
        },
        "timestamp": datetime.now().isoformat(),
    })


# ==================== WebSocket 事件处理 ====================

def register_websocket_handlers(socketio):
    """注册 WebSocket 事件处理器。

    Args:
        socketio: Flask-SocketIO 实例
    """

    @socketio.on("connect", namespace="/ws")
    def handle_connect():
        """WebSocket 连接建立事件"""
        logger.info(f"WebSocket 客户端已连接")
        emit("connected", {
            "message": "已连接到AI钓鱼检测服务",
            "timestamp": datetime.now().isoformat(),
        })

    @socketio.on("disconnect", namespace="/ws")
    def handle_disconnect():
        """WebSocket 连接断开事件"""
        logger.info(f"WebSocket 客户端已断开")

    @socketio.on("reload_model", namespace="/ws")
    def handle_reload_model():
        """WebSocket 模型热更新事件"""
        detector = get_hybrid_detector()
        try:
            detector.reload_model()
            emit("model_reload_result", {
                "status": "ok",
                "url_cnn_loaded": detector.url_cnn_loaded,
                "message": "模型已重新加载" if detector.url_cnn_loaded else "模型加载失败",
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            emit("model_reload_result", {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            })

    @socketio.on("detect_url", namespace="/ws")
    def handle_detect_url(data):
        """WebSocket 检测请求事件。

        接收数据: {"url": "https://..."}
        推送结果: detect_result 事件
        """
        try:
            url = data.get("url", "").strip() if isinstance(data, dict) else ""
            if not url:
                emit("error", {"message": "URL不能为空"})
                return

            # 自动补全协议
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            if not is_valid_url(url):
                emit("error", {"message": f"无效的URL: {url}", "url": url})
                return

            normalized_url = normalize_url(url)
            detector = get_hybrid_detector()

            # 规则引擎初筛
            rule_result = detector.rule_engine.analyze(normalized_url)
            rule_score = rule_result.get("rule_score", 0)

            # 发送规则引擎进度
            emit("detection_progress", {
                "url": normalized_url,
                "stage": "rule_engine",
                "rule_score": rule_score,
                "risk_level": rule_result.get("risk_level", "low"),
            })

            # 完整检测
            result = detector.detect(
                url=normalized_url,
                rule_result=rule_result,
            )

            # 推送最终结果
            emit("detect_result", result)
            logger.info(f"WebSocket检测完成: {url[:80]}")

        except Exception as e:
            logger.error(f"WebSocket检测异常: {e}\n{traceback.format_exc()}")
            emit("error", {
                "message": f"检测失败: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            })