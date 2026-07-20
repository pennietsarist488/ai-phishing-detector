"""
模型模块

包含两个核心模型:
    - URLCNNBiLSTM: URL 字符级 CNN + Bi-LSTM 深度学习模型
    - HybridDetector: 混合决策检测器，融合规则引擎、CNN、表单分析结果

融合权重（v2 版本）:
    - 规则引擎: 0.40
    - URL CNN+BiLSTM: 0.40
    - 表单分析: 0.20

动态权重分配:
    当某个模块缺失时（如CNN未加载），其权重按比例分配给其他模块。
"""