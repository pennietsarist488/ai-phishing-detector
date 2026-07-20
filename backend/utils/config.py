"""
AI钓鱼网站检测后端 - 配置模块
集中管理所有配置参数，支持环境变量覆盖

环境变量覆盖机制:
    - 类属性定义的默认值作为基础配置
    - 同名环境变量可覆盖默认值
    - 优先级: 环境变量 > 类属性默认值

使用方式:
    from backend.utils.config import Config
    
    # 读取配置（自动处理环境变量覆盖）
    port = Config.BACKEND_PORT
    
    # 通过环境变量覆盖（在启动前设置）
    import os
    os.environ["BACKEND_PORT"] = "8080"
"""

import os


class Config:
    """全局配置类，包含服务运行参数、模型路径、检测阈值和已知品牌/可疑域名列表。

    所有配置项均支持通过同名环境变量覆盖，优先级：环境变量 > 类属性默认值。
    
    注意：
        类属性直接定义的值是默认配置，环境变量覆盖通过 __getattr__ 实现。
        对于需要类型转换的配置项（如 int、float），在类属性中已预先处理环境变量。
    """

    def __getattr__(self, name):
        """支持通过环境变量覆盖类属性默认值。
        
        当访问的属性未在类中定义时，尝试从环境变量获取。
        这实现了环境变量优先级高于默认值的机制。
        
        Args:
            name: 配置项名称
            
        Returns:
            环境变量值（如果存在）
            
        Raises:
            AttributeError: 配置项不存在且环境变量也未设置
        """
        # 注意：此方法仅在类属性不存在时触发
        # 类属性中已定义的配置项不会触发此方法（除非通过实例访问）
        value = os.environ.get(name)
        if value is not None:
            return value
        raise AttributeError(f"'Config' object has no attribute '{name}'")

    # ==================== 服务配置 ====================
    BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
    BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "5000"))
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

    # ==================== 模型文件目录 ====================
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    MODEL_DIR = os.environ.get("MODEL_DIR", os.path.join(os.path.dirname(_BASE_DIR), "models"))

    # URL CNN+BiLSTM 模型文件路径
    URL_CNN_MODEL_PATH = os.environ.get("URL_CNN_MODEL_PATH",
        os.path.join(MODEL_DIR, "url_cnn.pth"))

    # ==================== URL处理参数 ====================
    URL_MAX_LEN = int(os.environ.get("URL_MAX_LEN", "200"))

    # ==================== 页面加载超时 ====================
    PAGE_LOAD_TIMEOUT = int(os.environ.get("PAGE_LOAD_TIMEOUT", "15"))

    # ==================== 规则引擎阈值 ====================
    RULE_HIGH_RISK_THRESHOLD = int(os.environ.get("RULE_HIGH_RISK_THRESHOLD", "60"))
    RULE_LOW_RISK_THRESHOLD = int(os.environ.get("RULE_LOW_RISK_THRESHOLD", "30"))

    # ==================== 已知品牌域名（用于域名相似度检测） ====================
    KNOWN_BRANDS = [
        "google", "facebook", "apple", "amazon", "microsoft", "paypal",
        "netflix", "instagram", "twitter", "linkedin", "dropbox", "adobe",
        "alibaba", "taobao", "jd", "baidu", "tencent", "qq",
        "weibo", "zhihu", "github", "gitlab", "bitbucket",
        "yahoo", "ebay", "aliexpress", "whatsapp", "telegram",
        "spotify", "twitch", "discord", "slack", "zoom",
        "bankofamerica", "chase", "wellsfargo", "citibank",
        "icbc", "ccb", "abc", "boc", "cmbchina",
    ]

    # ==================== 可疑顶级域名列表（常被用于钓鱼攻击） ====================
    SUSPICIOUS_TLDS = [
        ".tk", ".ml", ".ga", ".cf", ".gq",     # Freenom免费域名
        ".xyz", ".top", ".club", ".online",     # 廉价域名
        ".site", ".website", ".space", ".fun",
        ".work", ".tech", ".loan", ".win",
        ".bid", ".trade", ".webcam", ".date",
        ".download", ".review", ".country",
    ]

    # ==================== URL可疑关键词列表 ====================
    SUSPICIOUS_KEYWORDS = [
        "login", "signin", "logon", "verify", "update", "account",
        "secure", "security", "confirm", "bank", "banking", "paypal",
        "password", "credential", "recover", "unlock", "unlock",
        "billing", "invoice", "payment", "authorize", "authenticate",
        "validation", "limited", "suspended", "reactivate",
    ]

    # ==================== 表单敏感字段关键词 ====================
    SENSITIVE_FORM_FIELDS = [
        "password", "passwd", "pwd", "credit", "card", "ccv",
        "cvv", "cvc", "ssn", "social", "bank", "account",
        "routing", "cardnumber", "card_number", "cvv2",
        "身份证", "手机", "phone", "id_number", "idnumber",
        "pin", "secret", "token", "passcode",
    ]

    # ==================== 混合模型融合权重 ====================
    RULE_WEIGHT = float(os.environ.get("RULE_WEIGHT", "0.40"))
    URL_CNN_WEIGHT = float(os.environ.get("URL_CNN_WEIGHT", "0.40"))
    FORM_WEIGHT = float(os.environ.get("FORM_WEIGHT", "0.20"))