"""
AI钓鱼网站检测后端 - 规则引擎
基于静态规则的快速初筛模块，对URL进行多维度的特征匹配和风险评分
"""

import logging
import re
from urllib.parse import urlparse

from ..utils.url_utils import extract_url_features, compute_domain_similarity
from ..utils.config import Config

logger = logging.getLogger(__name__)


class RuleEngine:
    """规则引擎：通过一系列静态规则对URL进行快速风险评估。

    每条规则独立检测一种钓鱼特征，匹配后累加权重分，
    最终根据总分判断风险等级(low / suspicious / high)。
    """

    # ==================== 已知品牌域名 ====================
    KNOWN_BRANDS = Config.KNOWN_BRANDS

    # ==================== 可疑TLD列表 ====================
    SUSPICIOUS_TLDS = Config.SUSPICIOUS_TLDS

    # ==================== 可疑关键词 ====================
    SUSPICIOUS_KEYWORDS = Config.SUSPICIOUS_KEYWORDS

    # ==================== 规则权重配置 ====================
    WEIGHT_IP_DOMAIN = 20        # 使用IP地址代替域名
    WEIGHT_SUSPICIOUS_KEYWORD = 15  # 每个可疑关键词
    WEIGHT_DOMAIN_SIMILARITY = 15   # 域名相似度
    WEIGHT_URL_LENGTH = 10         # 过长URL
    WEIGHT_SUSPICIOUS_TLD = 15     # 可疑TLD
    WEIGHT_SPECIAL_CHARS = 10      # 特殊字符比例过高
    WEIGHT_NO_HTTPS = 10           # 未使用HTTPS
    WEIGHT_AT_SYMBOL = 20          # @符号
    WEIGHT_DOUBLE_SLASH = 15       # 双斜杠重定向
    WEIGHT_SUBDOMAIN_COUNT = 10    # 过多子域名

    # ==================== 各项检测阈值 ====================
    URL_LENGTH_THRESHOLD = 75         # URL长度超过此值视为过长
    SPECIAL_CHAR_RATIO_THRESHOLD = 0.15  # 特殊字符比例超过此值触发
    SUBDOMAIN_COUNT_THRESHOLD = 3     # 子域名数量超过此值触发
    DOUBLE_SLASH_THRESHOLD = 1        # 额外双斜杠数量（排除协议部分）

    def __init__(self):
        """初始化规则引擎"""
        pass

    # ==================== 单项检测方法 ====================

    def check_ip_instead_of_domain(self, url: str) -> dict:
        """检测URL是否使用IP地址代替域名。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int}
        """
        features = extract_url_features(url)
        matched = features.get("is_ip", False)
        detail = ""
        if matched:
            detail = f"URL使用IP地址({features['hostname']})代替域名"
        return {
            "matched": matched,
            "rule": "ip_instead_of_domain",
            "detail": detail,
            "weight": self.WEIGHT_IP_DOMAIN if matched else 0,
        }

    def check_suspicious_keywords(self, url: str) -> dict:
        """检测URL中是否包含可疑关键词（login/verify/account等）。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "matched_keywords": list}
        """
        url_lower = url.lower()
        matched_keywords = []
        for keyword in self.SUSPICIOUS_KEYWORDS:
            if keyword in url_lower:
                matched_keywords.append(keyword)

        matched = len(matched_keywords) > 0
        detail = ""
        weight = 0
        if matched:
            # 每个匹配的关键词累加权重
            weight = min(len(matched_keywords) * self.WEIGHT_SUSPICIOUS_KEYWORD, 45)
            detail = f"URL中包含可疑关键词: {', '.join(matched_keywords)}"

        return {
            "matched": matched,
            "rule": "suspicious_keywords",
            "detail": detail,
            "weight": weight,
            "matched_keywords": matched_keywords,
        }

    def check_domain_similarity(self, url: str) -> dict:
        """检测URL的域名与知名品牌域名的相似度。

        例如: gooogle.com 与 google.com 高度相似 → 判定为钓鱼。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "best_match": str}
        """
        features = extract_url_features(url)
        domain = features.get("domain", "")
        if not domain:
            return {
                "matched": False,
                "rule": "domain_similarity",
                "detail": "无法提取域名",
                "weight": 0,
                "best_match": None,
            }

        similarity = compute_domain_similarity(domain, self.KNOWN_BRANDS)
        matched = similarity.get("suspicious", False)
        detail = ""
        if matched:
            detail = (
                f"域名 '{domain}' 与 '{similarity['best_match']}' "
                f"相似度={similarity['similarity_score']}，可能为仿冒域名"
            )

        return {
            "matched": matched,
            "rule": "domain_similarity",
            "detail": detail,
            "weight": self.WEIGHT_DOMAIN_SIMILARITY if matched else 0,
            "best_match": similarity.get("best_match"),
            "similarity_score": similarity.get("similarity_score", 0),
        }

    def check_url_length(self, url: str) -> dict:
        """检测URL是否过长（常被用于隐藏恶意参数）。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "url_length": int}
        """
        url_len = len(url)
        matched = url_len > self.URL_LENGTH_THRESHOLD
        detail = ""
        if matched:
            detail = f"URL长度({url_len})超过阈值({self.URL_LENGTH_THRESHOLD})"

        return {
            "matched": matched,
            "rule": "url_length",
            "detail": detail,
            "weight": self.WEIGHT_URL_LENGTH if matched else 0,
            "url_length": url_len,
        }

    def check_suspicious_tld(self, url: str) -> dict:
        """检测URL是否使用可疑顶级域名（.tk/.ml/.ga等免费/廉价域名）。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "tld": str}
        """
        features = extract_url_features(url)
        tld = features.get("tld", "").lower()
        matched = tld in self.SUSPICIOUS_TLDS
        detail = ""
        if matched:
            detail = f"URL使用可疑顶级域名: {tld}"

        return {
            "matched": matched,
            "rule": "suspicious_tld",
            "detail": detail,
            "weight": self.WEIGHT_SUSPICIOUS_TLD if matched else 0,
            "tld": tld,
        }

    def check_special_chars(self, url: str) -> dict:
        """检测URL中特殊字符比例是否过高。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "ratio": float}
        """
        features = extract_url_features(url)
        ratio = features.get("special_char_ratio", 0)
        matched = ratio > self.SPECIAL_CHAR_RATIO_THRESHOLD
        detail = ""
        if matched:
            detail = f"URL特殊字符比例({ratio:.2%})超过阈值({self.SPECIAL_CHAR_RATIO_THRESHOLD:.0%})"

        return {
            "matched": matched,
            "rule": "special_chars",
            "detail": detail,
            "weight": self.WEIGHT_SPECIAL_CHARS if matched else 0,
            "special_char_ratio": ratio,
        }

    def check_https(self, url: str) -> dict:
        """检测URL是否使用HTTPS协议。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "is_https": bool}
        """
        features = extract_url_features(url)
        is_https = features.get("is_https", False)
        matched = not is_https
        detail = ""
        if matched:
            detail = "URL未使用HTTPS加密协议"

        return {
            "matched": matched,
            "rule": "no_https",
            "detail": detail,
            "weight": self.WEIGHT_NO_HTTPS if matched else 0,
            "is_https": is_https,
        }

    def check_at_symbol(self, url: str) -> dict:
        """检测URL中是否包含@符号（常用于伪装合法URL后跳转至恶意地址）。

        例如: https://google.com@evil.com → 实际访问 evil.com

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int}
        """
        matched = "@" in url
        detail = ""
        if matched:
            detail = "URL中包含@符号，可能存在地址伪装"

        return {
            "matched": matched,
            "rule": "at_symbol",
            "detail": detail,
            "weight": self.WEIGHT_AT_SYMBOL if matched else 0,
        }

    def check_double_slash_redirect(self, url: str) -> dict:
        """检测URL中是否存在多余的双斜杠（可能用于重定向攻击）。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "count": int}
        """
        features = extract_url_features(url)
        double_slash_count = features.get("double_slash_count", 0)
        matched = double_slash_count > self.DOUBLE_SLASH_THRESHOLD
        detail = ""
        if matched:
            detail = f"URL中包含{double_slash_count}处异常双斜杠，可能存在重定向攻击"

        return {
            "matched": matched,
            "rule": "double_slash_redirect",
            "detail": detail,
            "weight": self.WEIGHT_DOUBLE_SLASH if matched else 0,
            "double_slash_count": double_slash_count,
        }

    def check_subdomain_count(self, url: str) -> dict:
        """检测URL中是否包含过多子域名（钓鱼站点常用多层子域名伪装）。

        Args:
            url: 待检测URL

        Returns:
            dict: {"matched": bool, "rule": str, "detail": str, "weight": int, "count": int}
        """
        features = extract_url_features(url)
        count = features.get("subdomain_count", 0)
        matched = count > self.SUBDOMAIN_COUNT_THRESHOLD
        detail = ""
        if matched:
            detail = f"URL包含{count}个子域名，超过阈值({self.SUBDOMAIN_COUNT_THRESHOLD})"

        return {
            "matched": matched,
            "rule": "subdomain_count",
            "detail": detail,
            "weight": self.WEIGHT_SUBDOMAIN_COUNT if matched else 0,
            "subdomain_count": count,
        }

    # ==================== 综合分析 ====================

    def analyze(self, url: str) -> dict:
        """对URL执行全部规则的检测，汇总评分并判定风险等级。

        Args:
            url: 待检测的URL字符串

        Returns:
            dict: {
                "url": str,                          # 原始URL
                "rule_score": int,                   # 规则评分 0-100
                "risk_level": str,                   # low / suspicious / high
                "matched_rules": list[dict],         # 命中的所有规则详情
                "total_rules_checked": int,          # 检查的规则总数
                "features": dict,                    # URL特征
            }
        """
        # 提取URL特征
        features = extract_url_features(url)

        # 执行所有检测规则
        all_results = [
            self.check_ip_instead_of_domain(url),
            self.check_suspicious_keywords(url),
            self.check_domain_similarity(url),
            self.check_url_length(url),
            self.check_suspicious_tld(url),
            self.check_special_chars(url),
            self.check_https(url),
            self.check_at_symbol(url),
            self.check_double_slash_redirect(url),
            self.check_subdomain_count(url),
        ]

        # 筛选命中的规则
        matched_rules = [r for r in all_results if r["matched"]]
        total_weight = sum(r["weight"] for r in matched_rules)

        # 规则评分上限100
        rule_score = min(total_weight, 100)

        # 判定风险等级
        if rule_score >= Config.RULE_HIGH_RISK_THRESHOLD:
            risk_level = "high"
        elif rule_score <= Config.RULE_LOW_RISK_THRESHOLD:
            risk_level = "low"
        else:
            risk_level = "suspicious"

        logger.info(
            f"规则引擎分析完成: url={url[:80]}, "
            f"score={rule_score}, level={risk_level}, "
            f"matched_rules={len(matched_rules)}"
        )

        return {
            "url": url,
            "rule_score": rule_score,
            "risk_level": risk_level,
            "matched_rules": matched_rules,
            "total_rules_checked": len(all_results),
            "features": features,
        }