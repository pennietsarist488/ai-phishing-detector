"""
URL CNN+BiLSTM 模型评估脚本

加载训练好的模型，在测试数据集上进行全面评估，
输出详细指标报告和混淆矩阵。

用法:
    python evaluate.py --data ../钓鱼网站URL数据集/PhiUSIIL_Phishing_URL_Dataset.csv
    python evaluate.py --data data/urls.csv --model ../models/url_cnn.pth
"""

import sys
import os
import argparse
import logging

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report,
    confusion_matrix, roc_curve
)

# 确保项目根目录在路径中
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.models.url_cnn import URLCNNBiLSTM
from training.train_url_cnn import URLDataset, load_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def evaluate_model(args):
    """加载模型并评估"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"评估设备: {device}")

    # 加载数据（只使用测试集部分）
    _, _, _, _, test_urls, test_labels = load_data(
        csv_path=args.data,
        flip_label=args.flip_label,
        deduplicate=True,
        augment=False,
        seed=args.seed,
    )

    test_dataset = URLDataset(test_urls, test_labels, max_len=args.max_len)
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0
    )

    logger.info(f"测试集大小: {len(test_dataset)}")

    # 加载模型
    model = URLCNNBiLSTM(
        num_chars=128,
        embedding_dim=args.embedding_dim,
        max_len=args.max_len,
        conv_channels=args.conv_channels,
        kernel_sizes=tuple(args.kernel_sizes),
        lstm_hidden=args.lstm_hidden,
        lstm_layers=args.lstm_layers,
        fc_hidden=args.fc_hidden,
        dropout=args.dropout,
        num_classes=2,
    ).to(device)

    if not os.path.exists(args.model):
        logger.error(f"模型文件不存在: {args.model}")
        return

    model.load_state_dict(torch.load(args.model, map_location=device))
    model.eval()
    logger.info(f"模型加载成功: {args.model}")

    # 推理
    all_targets = []
    all_probs = []
    all_preds = []

    with torch.no_grad():
        for inputs, targets in test_loader:
            inputs = inputs.to(device)
            outputs = model(inputs)
            probs = torch.softmax(outputs, dim=-1)

            all_targets.extend(targets.numpy().tolist())
            all_probs.extend(probs[:, 1].cpu().numpy().tolist())
            _, predicted = outputs.max(1)
            all_preds.extend(predicted.cpu().numpy().tolist())

    all_targets = np.array(all_targets)
    all_probs = np.array(all_probs)
    all_preds = np.array(all_preds)

    # 计算指标
    accuracy = accuracy_score(all_targets, all_preds)
    precision = precision_score(all_targets, all_preds, zero_division=0)
    recall = recall_score(all_targets, all_preds, zero_division=0)
    f1 = f1_score(all_targets, all_preds, zero_division=0)
    auc = roc_auc_score(all_targets, all_probs)

    # 输出结果
    print("\n" + "=" * 60)
    print("  URL CNN+BiLSTM 模型评估报告")
    print("=" * 60)
    print(f"  模型路径:   {args.model}")
    print(f"  测试数据:   {args.data}")
    print(f"  测试样本数: {len(test_dataset)}")
    print(f"  钓鱼样本:   {int(all_targets.sum())} ({all_targets.mean()*100:.1f}%)")
    print(f"  正常样本:   {int((1-all_targets).sum())} ({(1-all_targets).mean()*100:.1f}%)")
    print("-" * 60)
    print(f"  Accuracy:   {accuracy:.4f} ({accuracy*100:.2f}%)")
    print(f"  Precision:  {precision:.4f} ({precision*100:.2f}%)")
    print(f"  Recall:     {recall:.4f} ({recall*100:.2f}%)")
    print(f"  F1 Score:   {f1:.4f} ({f1*100:.2f}%)")
    print(f"  AUC-ROC:    {auc:.4f}")
    print("-" * 60)

    # 分类报告
    print("\n  详细分类报告:")
    print(classification_report(
        all_targets, all_preds,
        target_names=["Benign(正常)", "Phishing(钓鱼)"],
        digits=4
    ))

    # 混淆矩阵
    cm = confusion_matrix(all_targets, all_preds)
    print("  混淆矩阵:")
    print(f"              预测正常  预测钓鱼")
    print(f"  实际正常    {cm[0][0]:>8}  {cm[0][1]:>8}")
    print(f"  实际钓鱼    {cm[1][0]:>8}  {cm[1][1]:>8}")
    print("=" * 60)

    # 阈值分析
    print("\n  不同阈值下的指标:")
    print(f"  {'阈值':>6}  {'Precision':>10}  {'Recall':>8}  {'F1':>8}  {'Accuracy':>10}")
    print("  " + "-" * 50)
    for threshold in [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        preds_t = (all_probs >= threshold).astype(int)
        p = precision_score(all_targets, preds_t, zero_division=0)
        r = recall_score(all_targets, preds_t, zero_division=0)
        f = f1_score(all_targets, preds_t, zero_division=0)
        a = accuracy_score(all_targets, preds_t)
        print(f"  {threshold:>6.1f}  {p:>10.4f}  {r:>8.4f}  {f:>8.4f}  {a:>10.4f}")

    # 错误分析
    print("\n  错误分析:")
    false_positives = np.where((all_preds == 1) & (all_targets == 0))[0]
    false_negatives = np.where((all_preds == 0) & (all_targets == 1))[0]
    print(f"  误报(正常→钓鱼): {len(false_positives)} 条")
    print(f"  漏报(钓鱼→正常): {len(false_negatives)} 条")

    # 展示部分误报和漏报样本
    if len(false_positives) > 0:
        print("\n  误报样本（前5条）:")
        for idx in false_positives[:5]:
            print(f"    {test_urls[idx]}")

    if len(false_negatives) > 0:
        print("\n  漏报样本（前5条）:")
        for idx in false_negatives[:5]:
            print(f"    {test_urls[idx]}")

    print()


def main():
    parser = argparse.ArgumentParser(description="URL CNN+BiLSTM 模型评估脚本")

    # 数据参数
    parser.add_argument("--data", type=str, required=True,
                        help="测试数据CSV文件路径（需包含URL和label列）")
    parser.add_argument("--flip_label", action="store_true", default=True,
                        help="翻转label（PhiUSIIL数据集默认开启）")
    parser.add_argument("--no_flip_label", action="store_false", dest="flip_label",
                        help="不翻转label")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")

    # 模型参数（需与训练时一致）
    parser.add_argument("--model", type=str, default="../models/url_cnn.pth",
                        help="模型权重文件路径")
    parser.add_argument("--max_len", type=int, default=100)
    parser.add_argument("--embedding_dim", type=int, default=32)
    parser.add_argument("--conv_channels", type=int, default=128)
    parser.add_argument("--kernel_sizes", type=int, nargs='+', default=[3, 5, 7])
    parser.add_argument("--lstm_hidden", type=int, default=128)
    parser.add_argument("--lstm_layers", type=int, default=1)
    parser.add_argument("--fc_hidden", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.5)

    # 评估参数
    parser.add_argument("--batch_size", type=int, default=256, help="评估批大小")

    args = parser.parse_args()
    evaluate_model(args)


if __name__ == "__main__":
    main()
