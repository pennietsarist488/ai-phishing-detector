"""
API路由模块

提供 RESTful API 和 WebSocket 接口:
    - /api/health: 健康检查（含系统指标）
    - /api/detect: 单条 URL 检测
    - /api/detect-batch: 批量 URL 检测
    - /api/model/info: 模型状态查询
    - /api/model/reload: 模型热更新
    - WebSocket /ws: 实时检测通信

限流策略:
    - detect: 60 次/分钟
    - detect-batch: 10 次/分钟
"""