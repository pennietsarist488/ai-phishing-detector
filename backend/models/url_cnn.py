"""
AI钓鱼网站检测后端 - URL字符级CNN+BiLSTM模型
基于PyTorch的混合神经网络，对URL字符串进行字符级分析

架构: Embedding → 多尺度Conv1d → Bi-LSTM → FC → 二分类
"""

import logging
import os
from typing import Union, List

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class URLCNNBiLSTM(nn.Module):
    """URL字符级 CNN + Bi-LSTM 混合神经网络。

    架构流程:
        字符嵌入(32维) →
        Conv1d(k=3,128) → BN → ReLU → MaxPool
        Conv1d(k=5,128) → BN → ReLU → MaxPool
        Conv1d(k=7,128) → BN → ReLU → MaxPool
        → Concat(多尺度特征)
        → Bi-LSTM(128) → 取最后时步
        → FC(256) → BN → ReLU → Dropout(0.5) → FC(2)

    输入: URL字符串，最大长度100字符
    输出: [benign_score, phishing_score] 二分类概率
    """

    def __init__(
        self,
        num_chars: int = 128,
        embedding_dim: int = 32,
        max_len: int = 100,
        conv_channels: int = 128,
        kernel_sizes: tuple = (3, 5, 7),
        lstm_hidden: int = 128,
        lstm_layers: int = 1,
        fc_hidden: int = 256,
        dropout: float = 0.5,
        num_classes: int = 2,
    ):
        """初始化URL CNN+BiLSTM模型。

        Args:
            num_chars: 字符表大小（ASCII范围0-127）
            embedding_dim: 字符嵌入向量维度
            max_len: URL最大字符长度
            conv_channels: 卷积核数量
            kernel_sizes: 多尺度卷积核大小元组
            lstm_hidden: Bi-LSTM隐藏层维度
            lstm_layers: Bi-LSTM层数
            fc_hidden: 全连接层维度
            dropout: Dropout率
            num_classes: 分类数量
        """
        super(URLCNNBiLSTM, self).__init__()
        self.num_chars = num_chars
        self.embedding_dim = embedding_dim
        self.max_len = max_len
        self.conv_channels = conv_channels
        self.kernel_sizes = kernel_sizes
        self.lstm_hidden = lstm_hidden
        self.num_classes = num_classes

        # 字符嵌入层
        self.embedding = nn.Embedding(num_chars, embedding_dim, padding_idx=0)

        # 多尺度卷积块
        self.conv_blocks = nn.ModuleList()
        for ks in kernel_sizes:
            block = nn.Sequential(
                nn.Conv1d(embedding_dim, conv_channels, kernel_size=ks, padding=ks // 2),
                nn.BatchNorm1d(conv_channels),
                nn.ReLU(),
                nn.MaxPool1d(kernel_size=2),
            )
            self.conv_blocks.append(block)

        # 计算Bi-LSTM输入维度 = conv_channels * len(kernel_sizes)
        lstm_input_dim = conv_channels * len(kernel_sizes)

        # Bi-LSTM层
        self.bilstm = nn.LSTM(
            input_size=lstm_input_dim,
            hidden_size=lstm_hidden,
            num_layers=lstm_layers,
            batch_first=True,
            bidirectional=True,
        )

        # 全连接分类层
        self.fc1 = nn.Linear(lstm_hidden * 2, fc_hidden)  # *2 因为双向
        self.bn_fc = nn.BatchNorm1d(fc_hidden)
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(fc_hidden, num_classes)

        # 初始化权重
        self._init_weights()

    def _init_weights(self):
        """初始化网络权重"""
        for m in self.modules():
            if isinstance(m, nn.Conv1d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.BatchNorm1d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.LSTM):
                for name, param in m.named_parameters():
                    if 'weight' in name:
                        nn.init.orthogonal_(param)
                    elif 'bias' in name:
                        nn.init.constant_(param, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """前向传播。

        Args:
            x: 字符索引张量，形状 (batch_size, max_len)，dtype=long

        Returns:
            torch.Tensor: 形状 (batch_size, 2) 的 logits
        """
        # 字符嵌入: (batch, max_len) → (batch, max_len, embedding_dim)
        x = self.embedding(x)
        # 调整维度: (batch, max_len, embedding_dim) → (batch, embedding_dim, max_len)
        x = x.transpose(1, 2)

        # 多尺度卷积 + 拼接
        conv_outputs = []
        for conv_block in self.conv_blocks:
            out = conv_block(x)  # (batch, conv_channels, max_len//2)
            conv_outputs.append(out)

        # 拼接: (batch, conv_channels * num_kernels, max_len//2)
        x = torch.cat(conv_outputs, dim=1)

        # 调整维度供Bi-LSTM: (batch, seq_len, features)
        x = x.transpose(1, 2)  # (batch, max_len//2, conv_channels * num_kernels)

        # Bi-LSTM
        lstm_out, (h_n, _) = self.bilstm(x)
        # 取双向最后时步: h_n形状 (num_layers*2, batch, hidden)
        # 拼接正向和反向最后时步
        forward_h = h_n[-2]  # 正向最后一层
        backward_h = h_n[-1]  # 反向最后一层
        x = torch.cat([forward_h, backward_h], dim=1)  # (batch, hidden*2)

        # 全连接分类
        x = self.fc1(x)
        x = self.bn_fc(x)
        x = F.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)

        return x

    @staticmethod
    def encode_url(url: str, max_len: int = 100) -> torch.Tensor:
        """将URL字符串编码为字符索引张量。

        - 取每个字符的ASCII码（0-127范围内）
        - 超过127的字符映射为0
        - 短于max_len的URL用0填充
        - 超过max_len的URL截断

        Args:
            url: URL字符串
            max_len: 最大编码长度

        Returns:
            torch.Tensor: 形状 (max_len,) 的long类型张量
        """
        encoded = torch.zeros(max_len, dtype=torch.long)
        for i, char in enumerate(url[:max_len]):
            code = ord(char)
            if 0 <= code < 128:
                encoded[i] = code
        return encoded

    def predict(self, url: str) -> dict:
        """对单条URL进行预测，返回置信度分数。

        Args:
            url: 待检测的URL字符串

        Returns:
            dict: {
                "url": str,
                "phishing_confidence": float,  # 钓鱼概率 [0, 1]
                "benign_confidence": float,    # 安全概率 [0, 1]
                "prediction": str,             # "phishing" 或 "benign"
            }
        """
        self.eval()
        device = next(self.parameters()).device

        with torch.no_grad():
            encoded = self.encode_url(url, self.max_len).unsqueeze(0).to(device)
            logits = self.forward(encoded)
            probs = F.softmax(logits, dim=-1).cpu().numpy()[0]

        phishing_conf = float(probs[1])
        benign_conf = float(probs[0])
        prediction = "phishing" if phishing_conf > 0.5 else "benign"

        return {
            "url": url,
            "phishing_confidence": round(phishing_conf, 4),
            "benign_confidence": round(benign_conf, 4),
            "prediction": prediction,
        }

    def predict_batch(self, urls: List[str]) -> List[dict]:
        """批量预测多条URL。

        Args:
            urls: URL字符串列表

        Returns:
            list[dict]: 每条URL的预测结果
        """
        self.eval()
        device = next(self.parameters()).device

        batch_encoded = torch.stack(
            [self.encode_url(url, self.max_len) for url in urls]
        ).to(device)

        with torch.no_grad():
            logits = self.forward(batch_encoded)
            probs = F.softmax(logits, dim=-1).cpu().numpy()

        results = []
        for i, url in enumerate(urls):
            phishing_conf = float(probs[i, 1])
            benign_conf = float(probs[i, 0])
            results.append({
                "url": url,
                "phishing_confidence": round(phishing_conf, 4),
                "benign_confidence": round(benign_conf, 4),
                "prediction": "phishing" if phishing_conf > 0.5 else "benign",
            })

        return results

    def save(self, path: str):
        """保存模型权重到文件。

        Args:
            path: 保存路径
        """
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        torch.save(self.state_dict(), path)
        logger.info(f"URL CNN+BiLSTM模型已保存到: {path}")

    def load(self, path: str):
        """从文件加载预训练权重。

        Args:
            path: 模型权重文件路径
        """
        if os.path.exists(path):
            self.load_state_dict(torch.load(path, map_location="cpu"))
            logger.info(f"URL CNN+BiLSTM模型权重已加载: {path}")
        else:
            logger.warning(f"URL CNN+BiLSTM模型文件不存在: {path}")
