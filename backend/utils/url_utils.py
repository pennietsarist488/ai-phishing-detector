"""
AI钓鱼网站检测后端 - URL工具函数
提供URL解析、特征提取、规范化和域名相似度计算等功能
"""

import re
import unicodedata
from urllib.parse import urlparse, urljoin
from Levenshtein import distance as levenshtein_distance

from .config import Config


# ==================== URL有效性验证 ====================

def is_valid_url(url: str) -> bool:
    """验证给定的URL是否合法。

    Args:
        url: 待验证的URL字符串

    Returns:
        bool: URL是否合法
    """
    if not url or not isinstance(url, str):
        return False
    # 去掉首尾空白
    url = url.strip()
    if not url:
        return False
    # 检查是否以 http:// 或 https:// 开头
    regex = re.compile(
        r'^https?://'                          # 协议
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?'  # 域名
        r'|localhost'                          # localhost
        r'|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
        r'(?::\d+)?'                           # 可选端口
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(regex.match(url))


# ==================== URL规范化 ====================

def normalize_url(url: str) -> str:
    """对URL进行规范化处理：转小写、解码Unicode、去除默认端口、标准化路径等。

    Args:
        url: 原始URL字符串

    Returns:
        str: 规范化后的URL
    """
    if not url:
        return ""
    url = url.strip()
    # 转小写
    url = url.lower()
    # Unicode规范化（如全角字符转半角）
    url = unicodedata.normalize('NFKC', url)
    # 解析URL
    parsed = urlparse(url)
    # 标准化scheme和netloc
    scheme = parsed.scheme or "http"
    netloc = parsed.netloc
    # 去除默认端口
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    elif scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    # 标准化路径（去除多余斜杠）
    path = parsed.path
    if path:
        path = re.sub(r'/+', '/', path)
    else:
        path = "/"
    # 重建URL
    normalized = f"{scheme}://{netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
    return normalized


# ==================== URL特征提取 ====================

def extract_url_features(url: str) -> dict:
    """从URL中提取多维特征，用于规则引擎和模型检测。

    提取的特征包括：
    - 域名、路径、TLD、各级子域名
    - URL总长度、域名长度、路径长度
    - 是否使用IP地址、是否有@符号、是否有端口号
    - 子域名数量、点号数量、数字比例、特殊字符比例
    - 是否包含HTTPS

    Args:
        url: 待提取特征的URL字符串

    Returns:
        dict: 包含所有特征的字典
    """
    if not url:
        return _empty_features()

    url = url.strip()
    parsed = urlparse(url)

    # 协议
    scheme = parsed.scheme.lower() if parsed.scheme else "http"

    # 域名（netloc）
    netloc = parsed.netloc or ""
    hostname = parsed.hostname or ""

    # 路径、查询、片段
    path = parsed.path or ""
    query = parsed.query or ""
    fragment = parsed.fragment or ""

    # 是否为IP地址
    ip_pattern = re.compile(
        r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
    )
    is_ip = bool(ip_pattern.match(hostname)) if hostname else False

    # TLD提取
    tld = ""
    if hostname and not is_ip:
        parts = hostname.split(".")
        if len(parts) >= 2:
            tld = "." + parts[-1]
        # 处理二级TLD（如 .com.cn）
        if len(parts) >= 3 and len(parts[-2]) <= 3:
            tld = "." + parts[-2] + "." + parts[-1]

    # 子域名
    subdomains = []
    if hostname and not is_ip:
        parts = hostname.split(".")
        if len(parts) > 2:
            # 排除TLD和二级域名
            tld_parts = 1
            if len(parts) >= 3 and len(parts[-2]) <= 3:
                tld_parts = 2
            subdomain_end = len(parts) - tld_parts - 1  # 再减去主域名
            if subdomain_end > 0:
                subdomains = parts[:subdomain_end]

    # 域名（不含子域名）
    domain = ""
    if hostname and not is_ip:
        parts = hostname.split(".")
        tld_parts = 1
        if len(parts) >= 3 and len(parts[-2]) <= 3:
            tld_parts = 2
        if len(parts) >= tld_parts + 1:
            domain = parts[-(tld_parts + 1)]

    # 各类长度
    url_len = len(url)
    hostname_len = len(hostname)
    path_len = len(path)

    # @ 符号检测
    has_at = "@" in url

    # 端口号检测
    has_port = parsed.port is not None

    # 数字比例
    digit_count = sum(1 for c in url if c.isdigit())
    digit_ratio = digit_count / url_len if url_len > 0 else 0

    # 特殊字符（非字母数字非标准URL字符）
    normal_chars = set("abcdefghijklmnopqrstuvwxyz0123456789.-_/:?=&@#%")
    special_count = sum(1 for c in url if c not in normal_chars)
    special_ratio = special_count / url_len if url_len > 0 else 0

    # 点号数量
    dot_count = url.count(".")

    # 连字符数量（域名中）
    hyphen_count = hostname.count("-") if hostname else 0

    return {
        "url": url,
        "scheme": scheme,
        "hostname": hostname,
        "domain": domain,
        "tld": tld,
        "subdomains": subdomains,
        "subdomain_count": len(subdomains),
        "path": path,
        "query": query,
        "fragment": fragment,
        "url_length": url_len,
        "hostname_length": hostname_len,
        "path_length": path_len,
        "is_ip": is_ip,
        "has_at": has_at,
        "has_port": has_port,
        "is_https": scheme == "https",
        "dot_count": dot_count,
        "hyphen_count": hyphen_count,
        "digit_ratio": round(digit_ratio, 4),
        "special_char_ratio": round(special_ratio, 4),
        "double_slash_count": url.count("//") - 1,  # 减去协议部分的 //
    }


def _empty_features() -> dict:
    """返回空特征字典（URL无效时使用）"""
    return {
        "url": "",
        "scheme": "",
        "hostname": "",
        "domain": "",
        "tld": "",
        "subdomains": [],
        "subdomain_count": 0,
        "path": "",
        "query": "",
        "fragment": "",
        "url_length": 0,
        "hostname_length": 0,
        "path_length": 0,
        "is_ip": False,
        "has_at": False,
        "has_port": False,
        "is_https": False,
        "dot_count": 0,
        "hyphen_count": 0,
        "digit_ratio": 0.0,
        "special_char_ratio": 0.0,
        "double_slash_count": 0,
    }


# ==================== 域名相似度计算 ====================

def compute_domain_similarity(domain: str, known_domains: list = None) -> dict:
    """计算给定域名与已知品牌域名列表的编辑距离相似度。

    使用 Levenshtein 编辑距离算法，返回最佳匹配的品牌域名及相似度分数。

    Args:
        domain: 待检查的域名
        known_domains: 已知品牌域名列表，默认使用 Config.KNOWN_BRANDS

    Returns:
        dict: {
            "best_match": str,         # 最相似的品牌域名
            "similarity_score": float, # 相似度分数 (0-1, 越高越相似)
            "distance": int,           # Levenshtein 距离
            "suspicious": bool,        # 是否可疑（相似度超过阈值）
        }
    """
    if not domain:
        return {
            "best_match": None,
            "similarity_score": 0.0,
            "distance": 999,
            "suspicious": False,
        }

    if known_domains is None:
        known_domains = Config.KNOWN_BRANDS

    domain_lower = domain.lower().strip()
    best_match = None
    best_similarity = 0.0
    best_distance = 999

    for brand in known_domains:
        brand_lower = brand.lower()
        # 计算编辑距离
        dist = levenshtein_distance(domain_lower, brand_lower)
        # 转换为相似度分数：1 - (编辑距离 / 最长字符串长度)
        max_len = max(len(domain_lower), len(brand_lower))
        if max_len == 0:
            similarity = 1.0
        else:
            similarity = 1.0 - (dist / max_len)

        if similarity > best_similarity:
            best_similarity = similarity
            best_distance = dist
            best_match = brand

    # 相似度超过0.7视为可疑（如 gooogle 与 google）
    suspicious = best_similarity >= 0.7 and best_distance <= 3

    return {
        "best_match": best_match,
        "similarity_score": round(best_similarity, 4),
        "distance": best_distance,
        "suspicious": suspicious,
    }