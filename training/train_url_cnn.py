"""
URL CNN+BiLSTM 模型训练脚本

适配 PhiUSIIL Phishing URL Dataset 数据集格式:
    CSV文件，包含 URL 和 label 列
    label=1 表示正常(legitimate)，label=0 表示钓鱼(phishing)
    训练时自动翻转label使 1=phishing, 0=benign

用法:
    python train_url_cnn.py --data ../钓鱼网站URL数据集/PhiUSIIL_Phishing_URL_Dataset.csv
    python train_url_cnn.py --data data/urls.csv --epochs 20 --batch_size 128
"""

import sys
import os
import argparse
import logging
import json
import time
import random

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, classification_report, confusion_matrix
)

# 确保项目根目录在路径中
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _proj_root not in sys.path:
    sys.path.insert(0, _proj_root)

from backend.models.url_cnn import URLCNNBiLSTM

# ==================== 日志配置 ====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ==================== 数据集类 ====================

class URLDataset(Dataset):
    """URL字符级数据集"""

    def __init__(self, urls: list, labels: list, max_len: int = 100):
        self.urls = urls
        self.labels = labels
        self.max_len = max_len

    def __len__(self):
        return len(self.urls)

    def __getitem__(self, idx):
        url = self.urls[idx]
        label = self.labels[idx]
        encoded = URLCNNBiLSTM.encode_url(url, self.max_len)
        return encoded, torch.tensor(label, dtype=torch.long)


# ==================== 数据增强 ====================

# 常见合法URL路径模板（用于为短域名合法URL添加路径，平衡训练数据）
LEGITIMATE_PATHS = [
    "/search", "/home", "/index", "/about", "/contact",
    "/products", "/services", "/blog", "/news", "/faq",
    "/help", "/support", "/docs", "/api/v1", "/login",
    "/dashboard", "/profile", "/settings", "/account",
    "/wiki", "/forum", "/community", "/resources",
    "/items", "/catalog", "/shop", "/store", "/cart",
    "/user/profile", "/user/settings", "/app/home",
]

# 常见合法URL查询参数模板
LEGITIMATE_QUERIES = [
    "?q=test", "?id=123", "?page=1", "?lang=en",
    "?sort=date", "?view=list", "?mode=normal",
    "?category=general", "?type=all", "?status=active",
    "?q=hello", "?page=2&sort=relevance",
    "?ref=homepage", "?source=web", "?tab=overview",
    "?section=main", "?action=view", "?format=html",
]


def augment_url(url: str) -> str:
    """对URL进行随机增强变换。

    增强策略:
        - 随机移除www前缀
        - 随机切换http/https协议
        - 随机截断查询参数
    """
    import random

    # 随机移除www
    if random.random() < 0.3 and "www." in url:
        url = url.replace("www.", "", 1)

    # 随机切换协议
    if random.random() < 0.3:
        if url.startswith("https://"):
            url = "http://" + url[8:]
        elif url.startswith("http://"):
            url = "https://" + url[7:]

    # 随机截断查询参数
    if "?" in url and random.random() < 0.2:
        url = url.split("?")[0]

    return url


def augment_legitimate_url(url: str) -> str:
    """为合法URL添加路径和查询参数，平衡训练数据中URL结构分布。

    解决CNN模型对带路径/查询参数URL的误判问题：
    PhiUSIIL数据集中合法URL多为短域名（如 google.com），
    钓鱼URL多带路径参数（如 evil.com/login.php?account=locked），
    导致模型学到了"路径/查询参数≈钓鱼"的错误关联。

    通过为合法URL添加常见路径和查询参数，使模型学习到：
    路径和查询参数本身不是钓鱼的判据，关键在于域名和内容。
    """
    import random

    base_url = url

    # 移除已有的查询参数和片段
    if "?" in base_url:
        base_url = base_url.split("?")[0]
    if "#" in base_url:
        base_url = base_url.split("#")[0]

    # 随机添加路径（60%概率）
    if random.random() < 0.6:
        path = random.choice(LEGITIMATE_PATHS)
        if base_url.endswith("/"):
            base_url = base_url.rstrip("/") + path
        else:
            base_url += path

    # 随机添加查询参数（50%概率）
    if random.random() < 0.5:
        query = random.choice(LEGITIMATE_QUERIES)
        base_url += query

    return base_url


# ==================== 数据加载 ====================

def load_data(csv_path: str, flip_label: bool = True, deduplicate: bool = True,
              augment: bool = True, augment_ratio: float = 0.2, seed: int = 42):
    """加载并预处理CSV数据集。

    Args:
        csv_path: CSV文件路径
        flip_label: 是否翻转label（PhiUSIIL数据集: 1=正常,0=钓鱼 → 翻转为1=钓鱼,0=正常）
        deduplicate: 是否去重
        augment: 是否进行数据增强
        augment_ratio: 增强样本占训练集的比例
        seed: 随机种子

    Returns:
        train_urls, train_labels, val_urls, val_labels, test_urls, test_labels
    """
    logger.info(f"加载数据集: {csv_path}")
    df = pd.read_csv(csv_path)

    # 验证必要列
    if 'URL' not in df.columns or 'label' not in df.columns:
        raise ValueError("CSV文件必须包含 'URL' 和 'label' 列")

    # 去重
    if deduplicate:
        before = len(df)
        df = df.drop_duplicates(subset=['URL'])
        after = len(df)
        if before > after:
            logger.info(f"去重: {before} → {after} (移除 {before - after} 条重复)")

    urls = df['URL'].astype(str).tolist()
    labels = df['label'].tolist()

    # 翻转label: PhiUSIIL中 1=legitimate, 0=phishing → 翻转为 1=phishing, 0=benign
    if flip_label:
        labels = [1 - l for l in labels]
        logger.info("已翻转label: 1=phishing, 0=benign")

    # 统计
    phishing_count = sum(labels)
    benign_count = len(labels) - phishing_count
    logger.info(f"数据统计: 总计 {len(urls)} 条, 钓鱼 {phishing_count} ({phishing_count/len(labels)*100:.1f}%), "
                f"正常 {benign_count} ({benign_count/len(labels)*100:.1f}%)")

    # 分层划分: 70% train, 15% val, 15% test
    train_urls, temp_urls, train_labels, temp_labels = train_test_split(
        urls, labels, test_size=0.3, random_state=seed, stratify=labels
    )
    val_urls, test_urls, val_labels, test_labels = train_test_split(
        temp_urls, temp_labels, test_size=0.5, random_state=seed, stratify=temp_labels
    )

    logger.info(f"划分: 训练 {len(train_urls)}, 验证 {len(val_urls)}, 测试 {len(test_urls)}")

    # 数据增强（仅训练集）
    if augment and augment_ratio > 0:
        random.seed(seed)

        # 通用增强：随机变换（移除www、切换协议、截断查询参数）
        aug_count = int(len(train_urls) * augment_ratio)
        aug_indices = random.sample(range(len(train_urls)), min(aug_count, len(train_urls)))
        aug_urls = [augment_url(train_urls[i]) for i in aug_indices]
        aug_labels = [train_labels[i] for i in aug_indices]
        train_urls.extend(aug_urls)
        train_labels.extend(aug_labels)
        logger.info(f"通用数据增强: 新增 {len(aug_urls)} 条")

        # 合法URL路径/查询参数增强：为短域名合法URL添加路径和查询参数
        # 解决模型对带路径URL的误判问题
        benign_indices = [i for i, l in enumerate(train_labels) if l == 0]
        aug_benign_count = int(len(benign_indices) * 0.5)
        aug_benign_sample = random.sample(benign_indices, min(aug_benign_count, len(benign_indices)))
        aug_benign_urls = [augment_legitimate_url(train_urls[i]) for i in aug_benign_sample]
        aug_benign_labels = [0] * len(aug_benign_urls)
        train_urls.extend(aug_benign_urls)
        train_labels.extend(aug_benign_labels)
        logger.info(f"合法URL路径增强: 新增 {len(aug_benign_urls)} 条（添加路径/查询参数）")

        # 钓鱼URL HTTPS增强：为HTTP钓鱼URL添加HTTPS变体
        # 解决模型将HTTPS等同于安全的错误关联
        phishing_indices = [i for i, l in enumerate(train_labels) if l == 1]
        aug_phishing_count = int(len(phishing_indices) * 0.2)
        aug_phishing_sample = random.sample(phishing_indices, min(aug_phishing_count, len(phishing_indices)))
        aug_phishing_urls = []
        for i in aug_phishing_sample:
            url = train_urls[i]
            if url.startswith("http://"):
                url = "https://" + url[7:]
            elif not url.startswith("http"):
                url = "https://" + url
            aug_phishing_urls.append(url)
        aug_phishing_labels = [1] * len(aug_phishing_urls)
        train_urls.extend(aug_phishing_urls)
        train_labels.extend(aug_phishing_labels)
        logger.info(f"钓鱼URL HTTPS增强: 新增 {len(aug_phishing_urls)} 条")

        logger.info(f"数据增强完成: 训练集扩大到 {len(train_urls)} 条")

    return train_urls, train_labels, val_urls, val_labels, test_urls, test_labels


# ==================== 训练逻辑 ====================

def train_one_epoch(model, dataloader, criterion, optimizer, device, grad_clip_norm=1.0):
    """训练一个epoch"""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (inputs, targets) in enumerate(dataloader):
        inputs, targets = inputs.to(device), targets.to(device)

        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, targets)
        loss.backward()

        # 梯度裁剪
        if grad_clip_norm > 0:
            nn.utils.clip_grad_norm_(model.parameters(), grad_clip_norm)

        optimizer.step()

        total_loss += loss.item() * inputs.size(0)
        _, predicted = outputs.max(1)
        correct += predicted.eq(targets).sum().item()
        total += inputs.size(0)

    avg_loss = total_loss / total
    accuracy = correct / total
    return avg_loss, accuracy


def evaluate(model, dataloader, criterion, device):
    """评估模型"""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for inputs, targets in dataloader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, targets)

            total_loss += loss.item() * inputs.size(0)
            probs = torch.softmax(outputs, dim=-1)
            _, predicted = outputs.max(1)
            correct += predicted.eq(targets).sum().item()
            total += inputs.size(0)

            all_targets.extend(targets.cpu().numpy().tolist())
            all_probs.extend(probs[:, 1].cpu().numpy().tolist())

    avg_loss = total_loss / total
    accuracy = correct / total

    # 计算详细指标
    preds = [1 if p > 0.5 else 0 for p in all_probs]
    metrics = {
        "loss": round(avg_loss, 4),
        "accuracy": round(accuracy, 4),
        "precision": round(precision_score(all_targets, preds, zero_division=0), 4),
        "recall": round(recall_score(all_targets, preds, zero_division=0), 4),
        "f1": round(f1_score(all_targets, preds, zero_division=0), 4),
        "auc": round(roc_auc_score(all_targets, all_probs), 4) if len(set(all_targets)) > 1 else 0.0,
    }

    return metrics


def train(args):
    """主训练流程"""
    # 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"训练设备: {device}")

    # 加载数据
    train_urls, train_labels, val_urls, val_labels, test_urls, test_labels = load_data(
        csv_path=args.data,
        flip_label=args.flip_label,
        deduplicate=args.deduplicate,
        augment=args.augment,
        augment_ratio=args.augment_ratio,
        seed=args.seed,
    )

    # 创建数据集和数据加载器
    train_dataset = URLDataset(train_urls, train_labels, max_len=args.max_len)
    val_dataset = URLDataset(val_urls, val_labels, max_len=args.max_len)
    test_dataset = URLDataset(test_urls, test_labels, max_len=args.max_len)

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=0, pin_memory=True
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, pin_memory=True
    )
    test_loader = DataLoader(
        test_dataset, batch_size=args.batch_size, shuffle=False, num_workers=0, pin_memory=True
    )

    # 创建模型
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

    # 打印模型信息
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"模型参数量: 总计 {total_params:,}, 可训练 {trainable_params:,}")

    # 损失函数（带标签平滑）
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)

    # 优化器
    optimizer = optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )

    # 学习率调度器
    scheduler = optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.epochs, eta_min=1e-6
    )

    # 训练循环
    best_val_f1 = 0.0
    best_epoch = 0
    patience_counter = 0
    history = {
        "train_loss": [], "train_acc": [],
        "val_loss": [], "val_acc": [], "val_f1": [], "val_auc": [],
    }

    logger.info("=" * 60)
    logger.info("开始训练")
    logger.info("=" * 60)

    start_time = time.time()

    for epoch in range(1, args.epochs + 1):
        epoch_start = time.time()

        # 训练
        train_loss, train_acc = train_one_epoch(
            model, train_loader, criterion, optimizer, device, args.grad_clip_norm
        )

        # 验证
        val_metrics = evaluate(model, val_loader, criterion, device)

        # 更新学习率
        scheduler.step()

        epoch_time = time.time() - epoch_start

        # 记录历史
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_metrics["loss"])
        history["val_acc"].append(val_metrics["accuracy"])
        history["val_f1"].append(val_metrics["f1"])
        history["val_auc"].append(val_metrics["auc"])

        # 打印进度
        current_lr = optimizer.param_groups[0]['lr']
        logger.info(
            f"Epoch {epoch}/{args.epochs} ({epoch_time:.1f}s) | "
            f"LR: {current_lr:.2e} | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} Acc: {val_metrics['accuracy']:.4f} "
            f"F1: {val_metrics['f1']:.4f} AUC: {val_metrics['auc']:.4f}"
        )

        # 保存最佳模型
        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            best_epoch = epoch
            patience_counter = 0
            model.save(args.output)
            logger.info(f"  → 保存最佳模型 (F1: {best_val_f1:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= args.patience:
                logger.info(f"Early stopping: 验证F1连续 {args.patience} 轮未提升")
                break

    total_time = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"训练完成! 总耗时: {total_time:.1f}s, 最佳epoch: {best_epoch}, 最佳Val F1: {best_val_f1:.4f}")
    logger.info("=" * 60)

    # 加载最佳模型进行测试集评估
    logger.info("加载最佳模型，在测试集上评估...")
    model.load_state_dict(torch.load(args.output, map_location=device))
    test_metrics = evaluate(model, test_loader, criterion, device)

    logger.info("=" * 60)
    logger.info("测试集评估结果:")
    logger.info(f"  Accuracy:  {test_metrics['accuracy']:.4f}")
    logger.info(f"  Precision: {test_metrics['precision']:.4f}")
    logger.info(f"  Recall:    {test_metrics['recall']:.4f}")
    logger.info(f"  F1 Score:  {test_metrics['f1']:.4f}")
    logger.info(f"  AUC-ROC:   {test_metrics['auc']:.4f}")
    logger.info("=" * 60)

    # 保存训练历史
    history_path = os.path.join(os.path.dirname(args.output), "training_history.json")
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump({
            "model_config": {
                "num_chars": 128,
                "embedding_dim": args.embedding_dim,
                "max_len": args.max_len,
                "conv_channels": args.conv_channels,
                "kernel_sizes": args.kernel_sizes,
                "lstm_hidden": args.lstm_hidden,
                "lstm_layers": args.lstm_layers,
                "fc_hidden": args.fc_hidden,
                "dropout": args.dropout,
            },
            "train_args": {
                "data": args.data,
                "epochs": args.epochs,
                "batch_size": args.batch_size,
                "learning_rate": args.learning_rate,
                "weight_decay": args.weight_decay,
                "label_smoothing": args.label_smoothing,
            },
            "best_epoch": best_epoch,
            "best_val_f1": best_val_f1,
            "test_metrics": test_metrics,
            "history": history,
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"训练历史已保存到: {history_path}")

    return test_metrics


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(description="URL CNN+BiLSTM 模型训练脚本")

    # 数据参数
    parser.add_argument("--data", type=str, required=True,
                        help="训练数据CSV文件路径（需包含URL和label列）")
    parser.add_argument("--flip_label", action="store_true", default=True,
                        help="翻转label（PhiUSIIL数据集: 1=正常→0, 0=钓鱼→1）")
    parser.add_argument("--no_flip_label", action="store_false", dest="flip_label",
                        help="不翻转label")
    parser.add_argument("--deduplicate", action="store_true", default=True,
                        help="去重（默认开启）")
    parser.add_argument("--no_deduplicate", action="store_false", dest="deduplicate",
                        help="不去重")
    parser.add_argument("--augment", action="store_true", default=True,
                        help="数据增强（默认开启）")
    parser.add_argument("--no_augment", action="store_false", dest="augment",
                        help="不进行数据增强")
    parser.add_argument("--augment_ratio", type=float, default=0.2,
                        help="增强样本比例（默认0.2）")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")

    # 模型参数
    parser.add_argument("--max_len", type=int, default=100, help="URL最大长度（默认100）")
    parser.add_argument("--embedding_dim", type=int, default=32, help="嵌入维度（默认32）")
    parser.add_argument("--conv_channels", type=int, default=128, help="卷积核数量（默认128）")
    parser.add_argument("--kernel_sizes", type=int, nargs='+', default=[3, 5, 7],
                        help="卷积核尺寸列表（默认 3 5 7）")
    parser.add_argument("--lstm_hidden", type=int, default=128, help="LSTM隐藏维度（默认128）")
    parser.add_argument("--lstm_layers", type=int, default=1, help="LSTM层数（默认1）")
    parser.add_argument("--fc_hidden", type=int, default=256, help="全连接层维度（默认256）")
    parser.add_argument("--dropout", type=float, default=0.5, help="Dropout率（默认0.5）")

    # 训练参数
    parser.add_argument("--epochs", type=int, default=20, help="训练轮数（默认20）")
    parser.add_argument("--batch_size", type=int, default=128, help="批大小（默认128）")
    parser.add_argument("--learning_rate", type=float, default=1e-3, help="学习率（默认1e-3）")
    parser.add_argument("--weight_decay", type=float, default=1e-4, help="权重衰减（默认1e-4）")
    parser.add_argument("--label_smoothing", type=float, default=0.05, help="标签平滑（默认0.05）")
    parser.add_argument("--grad_clip_norm", type=float, default=1.0, help="梯度裁剪（默认1.0）")
    parser.add_argument("--patience", type=int, default=5, help="Early stopping耐心值（默认5）")

    # 输出参数
    parser.add_argument("--output", type=str, default="../models/url_cnn.pth",
                        help="模型输出路径（默认../models/url_cnn.pth）")

    args = parser.parse_args()

    # 确保输出目录存在
    os.makedirs(os.path.dirname(args.output) if os.path.dirname(args.output) else '.', exist_ok=True)

    # 设置随机种子
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    # 开始训练
    train(args)


if __name__ == "__main__":
    main()
