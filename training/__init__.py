"""
训练模块

包含 URL CNN+BiLSTM 模型的训练和评估脚本:
    - train_url_cnn.py: 模型训练脚本（支持数据增强、Early Stopping）
    - evaluate.py: 模型评估脚本（输出详细指标报告）

训练数据集格式要求:
    CSV 文件，包含 URL 和 label 列
    PhiUSIIL 数据集: label=1 表示正常，label=0 表示钓鱼
    训练时自动翻转 label

数据增强策略:
    - 通用增强: 移除 www、切换协议、截断查询参数
    - 合法 URL 路径增强: 为短域名添加常见路径和查询参数
    - 钓鱼 URL HTTPS 增强: 为 HTTP 钓鱼 URL 添加 HTTPS 变体

使用示例:
    # 训练模型
    python training/train_url_cnn.py --data data/urls.csv
    
    # 评估模型
    python training/evaluate.py --data data/urls.csv --model models/url_cnn.pth
"""