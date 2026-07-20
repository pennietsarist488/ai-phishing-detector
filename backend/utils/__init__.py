"""
工具模块

包含三个辅助模块:
    - config: 配置管理，所有配置项支持环境变量覆盖
    - middleware: 中间件（请求日志记录、API 限流、统一错误响应）
    - url_utils: URL 工具函数（有效性验证、规范化、特征提取、域名相似度计算）

环境变量覆盖优先级:
    环境变量 > 类属性默认值

例如:
    export BACKEND_PORT=8080
    export RULE_WEIGHT=0.5
"""