"""
AI钓鱼网站检测后端 - 混合决策模型
融合规则引擎、URL CNN+BiLSTM和表单分析的最终决策层
"""

import os
import logging
import threading
from datetime import datetime
from typing import Optional

import torch

from .url_cnn import URLCNNBiLSTM
from ..engine.rule_engine import RuleEngine
from ..engine.form_analyzer import FormAnalyzer
from ..utils.config import Config
from ..utils.url_utils import is_valid_url, normalize_url, extract_url_features

logger = logging.getLogger(__name__)


class HybridDetector:
    """混合决策检测器：融合多维度检测结果，输出最终风险评分。

    融合策略 (v2):
        - 规则引擎: 权重 0.40
        - URL CNN+BiLSTM: 权重 0.40（每次检测均执行）
        - 表单分析: 权重 0.20（量化为 0-100 分参与加权）

    动态权重分配:
        当某个模块缺失时（如CNN未加载、无表单数据），
        其权重按比例分配给实际参与的模块，确保融合始终有效。
    """

    def __init__(
        self,
        url_cnn_model_path: Optional[str] = None,
    ):
        """初始化混合检测器，加载各子模块。

        Args:
            url_cnn_model_path: URL CNN+BiLSTM 模型权重文件路径，None 使用默认配置
        """
        # 规则引擎（始终可用）
        self.rule_engine = RuleEngine()

        # 表单分析器（始终可用）
        self.form_analyzer = FormAnalyzer()

        # 设备选择
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # ==================== URL CNN+BiLSTM 模型 ====================
        self.url_cnn_model_path = url_cnn_model_path or Config.URL_CNN_MODEL_PATH
        self.url_cnn = URLCNNBiLSTM(
            num_chars=128, embedding_dim=32, max_len=100,
            conv_channels=128, kernel_sizes=(3, 5, 7),
            lstm_hidden=128, lstm_layers=1,
            fc_hidden=256, dropout=0.5, num_classes=2,
        ).to(self.device)
        self.url_cnn_loaded = self._try_load_model(
            self.url_cnn, self.url_cnn_model_path, "URL CNN+BiLSTM"
        )

        logger.info(
            f"HybridDetector 初始化完成: device={self.device}, "
            f"url_cnn_loaded={self.url_cnn_loaded}"
        )

    # ==================== 模型加载 ====================

    def _try_load_model(self, model, path: str, name: str) -> bool:
        """尝试加载模型权重。

        Args:
            model: PyTorch 模型实例
            path: 权重文件路径
            name: 模型名称（用于日志）

        Returns:
            bool: 是否成功加载
        """
        if os.path.exists(path):
            try:
                model.load_state_dict(torch.load(path, map_location=self.device))
                model.eval()
                logger.info(f"{name} 模型加载成功: {path}")
                return True
            except Exception as e:
                logger.error(f"{name} 模型加载失败: {e}，请检查权重文件是否匹配")
                return False
        else:
            logger.warning(
                f"{name} 模型文件不存在 ({path})，"
                f"CNN推理将被跳过，仅使用规则引擎检测。"
                f"请使用训练脚本训练模型后再放入该路径。"
            )
            return False

    def reload_model(self):
        """热更新模型：重新加载模型文件，无需重启服务。

        训练脚本生成新模型后，调用此方法即可替换当前模型。
        如果新模型加载失败，保留旧模型状态不变。
        """
        logger.info("正在热更新模型...")
        new_loaded = self._try_load_model(
            self.url_cnn, self.url_cnn_model_path, "URL CNN+BiLSTM"
        )
        if new_loaded:
            self.url_cnn_loaded = True
            logger.info("模型热更新成功")
        else:
            logger.warning("模型热更新失败，保留旧模型状态")

    # ==================== 域名信任机制 ====================

    # 已知品牌域名精确匹配时的CNN置信度衰减因子
    DOMAIN_TRUST_DECAY = 0.1

    # CNN推理超时时间（秒）
    CNN_INFERENCE_TIMEOUT = 5.0

    def _inference_with_timeout(self, url: str) -> Optional[dict]:
        """带超时保护的CNN推理。

        Args:
            url: 待检测URL

        Returns:
            推理结果字典，超时或失败返回 None
        """
        result_container = {"result": None, "error": None}

        def _run():
            try:
                result_container["result"] = self.url_cnn.predict(url)
            except Exception as e:
                result_container["error"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self.CNN_INFERENCE_TIMEOUT)

        if thread.is_alive():
            logger.warning(
                f"CNN推理超时 ({self.CNN_INFERENCE_TIMEOUT}s)，跳过本次推理"
            )
            return None

        if result_container["error"]:
            logger.error(f"CNN推理失败: {result_container['error']}")
            return None

        return result_container["result"]

    def _get_domain_trust_factor(self, url: str) -> float:
        """获取域名信任因子，用于调整CNN置信度。

        当URL的域名精确匹配已知品牌时，返回较低的衰减因子，
        以修正CNN模型对带路径/查询参数的正常URL的误判。

        原理：CNN模型从训练数据中学到了"路径/查询参数≈钓鱼"的错误关联，
        因为PhiUSIIL数据集中正常URL多为短域名，钓鱼URL多带路径参数。
        对于已知品牌域名的精确匹配（如 google.com/search?q=test），
        大幅降低CNN影响，让规则引擎主导判定。

        Args:
            url: 待检测的URL

        Returns:
            float: 0.0-1.0 的信任因子，1.0表示不调整
        """
        features = extract_url_features(url)
        domain = features.get("domain", "").lower()

        if not domain:
            return 1.0

        # 检查域名是否精确匹配已知品牌
        known_brands_lower = [b.lower() for b in Config.KNOWN_BRANDS]
        if domain in known_brands_lower:
            return self.DOMAIN_TRUST_DECAY

        return 1.0

    # ==================== 综合检测 ====================

    def detect(
        self,
        url: str,
        rule_result: Optional[dict] = None,
        form_result: Optional[dict] = None,
    ) -> dict:
        """执行完整的钓鱼网站检测流程。

        融合规则引擎、URL CNN+BiLSTM、表单分析三个维度的结果，
        输出最终的风险评分和检测结论。

        Args:
            url: 待检测的URL
            rule_result: 预先计算的规则引擎结果，为None时自动计算
            form_result: 预先计算的表单分析结果，为None时跳过

        Returns:
            dict: 完整的检测结果
        """
        # 规范化URL
        normalized_url = normalize_url(url) if url else url

        detection_stages = []
        timestamp = datetime.now().isoformat()

        # ==================== 阶段1: 规则引擎快速初筛 ====================
        detection_stages.append("rule_engine")
        if rule_result is None:
            rule_result = self.rule_engine.analyze(url)

        rule_score = rule_result.get("rule_score", 0)
        risk_level = rule_result.get("risk_level", "low")

        # ==================== 阶段2: URL CNN+BiLSTM 分析 ====================
        # 策略变更: 无论规则引擎评分高低，只要模型已加载就执行CNN推理
        url_cnn_result = None
        if self.url_cnn_loaded:
            detection_stages.append("url_cnn")
            try:
                url_cnn_result = self._inference_with_timeout(normalized_url)
            except Exception as e:
                logger.error(f"URL CNN+BiLSTM推理失败: {e}")
                url_cnn_result = None

        # ==================== 阶段3: 表单分析 ====================
        if form_result is not None:
            detection_stages.append("form_analysis")

        # ==================== 阶段4: 融合计算 ====================
        scores = []
        weights = []

        # 规则引擎: 固定权重
        scores.append(float(rule_score))
        weights.append(Config.RULE_WEIGHT)

        # URL CNN+BiLSTM: 固定权重（模型未加载时权重转移给规则引擎）
        domain_trust_factor = 1.0
        if url_cnn_result:
            # 应用域名信任因子：已知品牌域名精确匹配时降低CNN置信度
            domain_trust_factor = self._get_domain_trust_factor(url)
            cnn_phishing_score = url_cnn_result.get("phishing_confidence", 0) * 100
            if domain_trust_factor < 1.0:
                original_score = cnn_phishing_score
                cnn_phishing_score *= domain_trust_factor
                # 同步调整CNN结果（用于前端展示）
                url_cnn_result["phishing_confidence"] = round(
                    url_cnn_result["phishing_confidence"] * domain_trust_factor, 4
                )
                url_cnn_result["benign_confidence"] = round(
                    1.0 - url_cnn_result["phishing_confidence"], 4
                )
                url_cnn_result["prediction"] = (
                    "phishing" if url_cnn_result["phishing_confidence"] > 0.5 else "benign"
                )
                url_cnn_result["domain_trust_applied"] = True
                logger.info(
                    f"域名信任调整: trust_factor={domain_trust_factor}, "
                    f"CNN评分 {original_score:.1f} → {cnn_phishing_score:.1f}"
                )
            scores.append(cnn_phishing_score)
            weights.append(Config.URL_CNN_WEIGHT)
        else:
            weights[0] += Config.URL_CNN_WEIGHT

        # 表单分析: 固定权重（无表单数据时权重动态分配给其他模块）
        if form_result:
            form_score = self._compute_form_score(form_result)
            scores.append(form_score)
            weights.append(Config.FORM_WEIGHT)
        else:
            if sum(weights) > 0:
                redistribute = Config.FORM_WEIGHT / len(weights)
                for i in range(len(weights)):
                    weights[i] += redistribute

        # 计算最终加权评分（动态归一化）
        total_weight = sum(weights)
        final_risk_score = (
            sum(s * w for s, w in zip(scores, weights)) / total_weight
            if total_weight > 0 else rule_score
        )
        final_risk_score = min(max(round(final_risk_score), 0), 100)

        # 风险等级判定（基于融合后的最终评分）
        if final_risk_score >= Config.RULE_HIGH_RISK_THRESHOLD:
            final_risk_level = "high"
            is_phishing = True
            recommendation = "综合检测判定为高风险钓鱼网站，建议立即拦截"
        elif final_risk_score <= Config.RULE_LOW_RISK_THRESHOLD:
            final_risk_level = "low"
            is_phishing = False
            recommendation = "综合检测判定为低风险，建议放行"
        else:
            final_risk_level = "suspicious"
            is_phishing = final_risk_score >= 50
            recommendation = "综合检测结果为可疑，建议人工复核"

        logger.info(
            f"检测完成: url={url[:80]}, rule_score={rule_score}, "
            f"cnn_confidence={url_cnn_result.get('phishing_confidence', 0) if url_cnn_result else 'N/A'}, "
            f"final_score={final_risk_score}, level={final_risk_level}"
        )

        return self._build_result(
            url=url,
            normalized_url=normalized_url,
            timestamp=timestamp,
            rule_result=rule_result,
            url_cnn_result=url_cnn_result,
            form_result=form_result,
            detection_stages=detection_stages,
            final_risk_score=final_risk_score,
            risk_level=final_risk_level,
            is_phishing=is_phishing,
            recommendation=recommendation,
        )

    def _build_result(
        self,
        url: str,
        normalized_url: str,
        timestamp: str,
        rule_result: dict,
        url_cnn_result: Optional[dict],
        form_result: Optional[dict],
        detection_stages: list,
        final_risk_score: int,
        risk_level: str,
        is_phishing: bool,
        recommendation: str,
    ) -> dict:
        """构建标准化的检测结果字典。"""
        return {
            # 基本信息
            "url": url,
            "normalized_url": normalized_url,
            "timestamp": timestamp,
            "is_valid_url": is_valid_url(url),

            # 核心结论
            "final_risk_score": round(final_risk_score, 1),
            "risk_level": risk_level,
            "is_phishing": is_phishing,
            "recommendation": recommendation,

            # 规则引擎结果
            "rule_result": {
                "rule_score": rule_result.get("rule_score", 0),
                "risk_level": rule_result.get("risk_level", "low"),
                "matched_rules": [
                    {
                        "rule": r.get("rule", ""),
                        "detail": r.get("detail", ""),
                        "weight": r.get("weight", 0),
                    }
                    for r in rule_result.get("matched_rules", [])
                ],
                "total_rules_checked": rule_result.get("total_rules_checked", 0),
                "url_features": rule_result.get("features", {}),
            },

            # URL CNN+BiLSTM 结果（模型未加载或未执行推理时为None）
            "url_cnn_result": {
                "phishing_confidence": url_cnn_result.get("phishing_confidence", 0),
                "benign_confidence": url_cnn_result.get("benign_confidence", 0),
                "prediction": url_cnn_result.get("prediction", "unknown"),
                "domain_trust_applied": url_cnn_result.get("domain_trust_applied", False),
            } if url_cnn_result else None,

            # 模型加载状态（独立于是否有推理结果）
            "url_cnn_loaded": self.url_cnn_loaded,

            # 表单分析结果
            "form_analysis": {
                "has_sensitive_fields": form_result.get("has_sensitive_fields", False),
                "sensitive_field_types": form_result.get("sensitive_field_types", []),
                "form_count": form_result.get("form_count", 0),
                "input_count": form_result.get("input_count", 0),
                "overall_form_suspicious": form_result.get("overall_form_suspicious", False),
            } if form_result else None,

            # 检测流程信息
            "detection_stages": detection_stages,
        }

    def _compute_form_score(self, form_result: dict) -> float:
        """将表单分析结果量化为 0-100 的风险评分。

        量化标准:
            - 包含敏感字段（密码/信用卡等）: +50
            - 表单 action 指向外部域名: +30
            - 包含 2 个及以上表单: +10
            - 最高 100 分

        Args:
            form_result: 表单分析结果字典

        Returns:
            float: 0-100 的表单风险评分
        """
        if not form_result:
            return 0.0

        score = 0.0
        if form_result.get("has_sensitive_fields"):
            score += 50.0
        if form_result.get("overall_form_suspicious"):
            score += 30.0
        if form_result.get("form_count", 0) >= 2:
            score += 10.0

        return min(score, 100.0)
