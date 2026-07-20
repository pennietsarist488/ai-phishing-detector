"""
AI钓鱼网站检测后端服务包

模块结构:
    backend/
        app.py          - Flask 应用入口，服务启动逻辑
        api/
            routes.py   - RESTful API 路由定义
        models/
            url_cnn.py      - URL CNN+BiLSTM 模型定义
            hybrid_model.py - 混合决策模型（融合多维度检测结果）
        engine/
            rule_engine.py  - 规则引擎（静态规则检测）
            form_analyzer.py - 表单分析器（敏感字段检测）
            screenshotter.py - 无头浏览器页面内容提取
        utils/
            config.py       - 配置管理（支持环境变量覆盖）
            middleware.py   - 中间件（请求日志、限流）
            url_utils.py    - URL 工具函数（解析、特征提取）

技术栈:
    - Flask + Flask-SocketIO: Web 框架和 WebSocket 支持
    - PyTorch: 深度学习模型推理
    - Playwright: 无头浏览器（页面内容提取）
    - psutil: 系统监控

作者: AI钓鱼检测团队
版本: 1.0.0
"""