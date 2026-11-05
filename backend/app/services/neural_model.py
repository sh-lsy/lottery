"""
Lightweight multi-task neural network for Shuangseqiu lottery sequence learning.
Outputs joint probability distributions for 33 red balls and 16 blue balls.
Supports temporal Multi-Head Attention, Focal Loss optimization, and online incremental self-evolution.
Model weights are saved as a compact PyTorch checkpoint (< 1.5 MB).
"""

import os
from typing import List, Tuple, Optional, Dict
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from backend.app.models import DrawHistory


class BinaryFocalLossWithLogits(nn.Module):
    """
    Focal Loss for multi-label red ball imbalance.
    Suppresses well-classified negatives and prioritizes hard positive balls.
    """

    def __init__(self, alpha: float = 0.65, gamma: float = 2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
        probs = torch.sigmoid(logits)
        p_t = targets * probs + (1.0 - targets) * (1.0 - probs)
        alpha_t = targets * self.alpha + (1.0 - targets) * (1.0 - self.alpha)
        modulating = (1.0 - p_t) ** self.gamma
        return (alpha_t * modulating * bce).mean()


class SSQNeuralNet(nn.Module):
    """
    Compact multi-task deep neural network for sequence prediction with temporal Multi-Head Attention.
    Extracts chronological lottery dynamics across rolling draw history.
    Dual output heads predict Red ball probabilities (multi-label) and Blue ball (multi-class).
    """

    def __init__(
        self,
        input_dim: int = 55 * 15,
        hidden_dim1: int = 256,
        hidden_dim2: int = 128,
        num_heads: int = 4,
    ):
        super().__init__()
        self.window_size = 15
        self.feature_dim = 55
        self.input_dim = input_dim

        # Temporal sequence projection & position embedding
        self.input_proj = nn.Linear(55, hidden_dim2)
        self.pos_embed = nn.Parameter(torch.randn(1, 15, hidden_dim2) * 0.02)

        # Multi-head attention across time steps
        self.norm1 = nn.LayerNorm(hidden_dim2)
        self.attn = nn.MultiheadAttention(
            embed_dim=hidden_dim2,
            num_heads=num_heads,
            batch_first=True,
            dropout=0.1,
        )

        # Feed-forward residual block
        self.norm2 = nn.LayerNorm(hidden_dim2)
        self.ffn = nn.Sequential(
            nn.Linear(hidden_dim2, hidden_dim1),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim1, hidden_dim2),
        )

        # Dual Heads with normalization
        self.red_head = nn.Sequential(
            nn.Linear(hidden_dim2, 128),
            nn.LayerNorm(128),
            nn.GELU(),
            nn.Linear(128, 33),
        )
        self.blue_head = nn.Sequential(
            nn.Linear(hidden_dim2, 64),
            nn.LayerNorm(64),
            nn.GELU(),
            nn.Linear(64, 16),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        B = x.shape[0]
        x_seq = x.view(B, self.window_size, self.feature_dim)
        h = self.input_proj(x_seq) + self.pos_embed

        attn_out, _ = self.attn(h, h, h)
        h = self.norm1(h + attn_out)
        h = self.norm2(h + self.ffn(h))

        # Weighted combination of temporal mean and latest state
        pooled = 0.5 * h.mean(dim=1) + 0.5 * h[:, -1, :]
        red_logits = self.red_head(pooled)
        blue_logits = self.blue_head(pooled)
        return red_logits, blue_logits


class SSQNeuralPredictor:
    """Orchestrates feature encoding, dataset construction, training, inference, and online evolution."""

    def __init__(
        self,
        model_path: str = "data/ssq_neural_model.pt",
        window_size: int = 15,
        device: str = "cpu",
    ):
        self.model_path = model_path
        self.window_size = window_size
        self.device = torch.device(device)
        self.input_dim = 55 * window_size

        self.model = SSQNeuralNet(input_dim=self.input_dim).to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)

        if os.path.exists(self.model_path):
            try:
                self.load_model(self.model_path)
            except Exception:
                pass

    @staticmethod
    def encode_single_draw(draw: DrawHistory) -> np.ndarray:
        """
        Encodes a single draw into a normalized 55-dimensional feature vector:
        - 33 binary indicators for red balls
        - 16 binary indicators for blue ball
        - 6 normalized scalar metrics (sum, span, ac, odd_ratio, prime_ratio, zone1_ratio)
        """
        vec = np.zeros(55, dtype=np.float32)
        # Red balls (1..33)
        for r in draw.reds:
            if 1 <= r <= 33:
                vec[r - 1] = 1.0
        # Blue ball (1..16)
        if 1 <= draw.blue_1 <= 16:
            vec[33 + draw.blue_1 - 1] = 1.0

        # Derived metrics
        reds = draw.reds
        s = sum(reds)
        span = reds[-1] - reds[0]
        # AC value
        diffs = {abs(reds[i] - reds[j]) for i in range(len(reds)) for j in range(i + 1, len(reds))}
        ac = len(diffs) - (len(reds) - 1)
        odd_count = sum(1 for x in reds if x % 2 == 1)
        primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}
        prime_count = sum(1 for x in reds if x in primes)
        z1_count = sum(1 for x in reds if x <= 11)

        vec[49] = (s - 102.0) / 30.0
        vec[50] = (span - 24.0) / 6.0
        vec[51] = (ac - 6.5) / 2.0
        vec[52] = (odd_count - 3.0) / 1.5
        vec[53] = (prime_count - 2.0) / 1.2
        vec[54] = (z1_count - 2.0) / 1.2
        return vec

    def build_dataset(self, draws: List[DrawHistory]) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Constructs rolling window dataset from chronological draws.
        Returns:
            X: Tensor of shape (N, 55 * window_size)
            y_red: Tensor of shape (N, 33), binary multi-label targets
            y_blue: Tensor of shape (N,), multi-class indices (0..15)
        """
        if len(draws) <= self.window_size:
            raise ValueError(f"Need at least {self.window_size + 1} draws to build dataset.")

        encoded_all = [self.encode_single_draw(d) for d in draws]
        X_list, y_red_list, y_blue_list = [], [], []

        for i in range(self.window_size, len(draws)):
            feat_window = np.concatenate(encoded_all[i - self.window_size : i], axis=0)
            X_list.append(feat_window)

            target_red = np.zeros(33, dtype=np.float32)
            for r in draws[i].reds:
                if 1 <= r <= 33:
                    target_red[r - 1] = 1.0
            y_red_list.append(target_red)
            y_blue_list.append(draws[i].blue_1 - 1)

        X = torch.tensor(np.array(X_list), dtype=torch.float32, device=self.device)
        y_red = torch.tensor(np.array(y_red_list), dtype=torch.float32, device=self.device)
        y_blue = torch.tensor(np.array(y_blue_list), dtype=torch.long, device=self.device)
        return X, y_red, y_blue

    def train_base_model(
        self,
        draws: List[DrawHistory],
        epochs: int = 20,
        batch_size: int = 64,
        lr: float = 2e-3,
        verbose: bool = True,
    ) -> Dict[str, float]:
        """
        Trains model from scratch on historical dataset (e.g. first 3300 draws)
        with Focal Loss and Cosine Annealing learning rate schedule.
        Saves checkpoint to self.model_path upon completion.
        """
        if len(draws) <= self.window_size + 10:
            raise ValueError(f"Need more than {self.window_size + 10} draws to train.")

        X, y_red, y_blue = self.build_dataset(draws)
        n_samples = X.shape[0]

        self.model.train()
        criterion_red = BinaryFocalLossWithLogits(alpha=0.65, gamma=2.0)
        criterion_blue = nn.CrossEntropyLoss()
        optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-4)

        final_loss = 0.0
        for ep in range(epochs):
            perm = torch.randperm(n_samples)
            epoch_loss = 0.0
            steps = 0
            for b_start in range(0, n_samples, batch_size):
                b_idx = perm[b_start : b_start + batch_size]
                bx, by_r, by_b = X[b_idx], y_red[b_idx], y_blue[b_idx]

                optimizer.zero_grad()
                pred_r, pred_b = self.model(bx)
                loss_r = criterion_red(pred_r, by_r)
                loss_b = criterion_blue(pred_b, by_b)
                loss = loss_r * 2.0 + loss_b * 1.5

                loss.backward()
                optimizer.step()

                epoch_loss += loss.item()
                steps += 1

            scheduler.step()
            avg_loss = epoch_loss / max(1, steps)
            final_loss = avg_loss
            if verbose and (ep + 1) % 5 == 0:
                print(f"[SSQNeuralNet] Epoch {ep+1}/{epochs} - Loss: {avg_loss:.4f} - LR: {scheduler.get_last_lr()[0]:.6f}")

        self.save_model(self.model_path)
        return {"final_loss": final_loss, "epochs": epochs, "samples": n_samples}

    def predict_probabilities(self, historical_draws: List[DrawHistory]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Takes chronological history up to T-1 and predicts probabilities for draw T.
        Returns:
            red_probs: np.ndarray of shape (33,), calibrated probabilities in [0, 1]
            blue_probs: np.ndarray of shape (16,), normalized probabilities summing to 1.0
        """
        if len(historical_draws) < self.window_size:
            return np.ones(33) / 33.0, np.ones(16) / 16.0

        encoded_window = [self.encode_single_draw(d) for d in historical_draws[-self.window_size :]]
        x_flat = np.concatenate(encoded_window).astype(np.float32)
        x_tensor = torch.tensor(x_flat, dtype=torch.float32, device=self.device).unsqueeze(0)

        self.model.eval()
        with torch.no_grad():
            red_logits, blue_logits = self.model(x_tensor)
            red_probs = torch.sigmoid(red_logits).cpu().numpy().squeeze(0)
            blue_probs = torch.softmax(blue_logits, dim=-1).cpu().numpy().squeeze(0)

        return red_probs, blue_probs

    def online_update(
        self,
        actual_draw: DrawHistory,
        history_prior: List[DrawHistory],
        lr: float = 1e-4,
        steps: int = 1,
    ) -> float:
        """
        Online learning step: updates neural network weights given the authentic draw outcome.
        Executes gradient steps on CPU (typically < 30ms) and saves updated checkpoint.
        Returns loss value.
        """
        if len(history_prior) < self.window_size:
            return 0.0

        encoded_window = [self.encode_single_draw(d) for d in history_prior[-self.window_size :]]
        x_flat = np.concatenate(encoded_window).astype(np.float32)
        x_tensor = torch.tensor(x_flat, dtype=torch.float32, device=self.device).unsqueeze(0)

        target_red = np.zeros(33, dtype=np.float32)
        for r in actual_draw.reds:
            if 1 <= r <= 33:
                target_red[r - 1] = 1.0
        y_r = torch.tensor(target_red, dtype=torch.float32, device=self.device).unsqueeze(0)
        y_b = torch.tensor([actual_draw.blue_1 - 1], dtype=torch.long, device=self.device)

        self.model.train()
        criterion_red = BinaryFocalLossWithLogits(alpha=0.65, gamma=2.0)
        criterion_blue = nn.CrossEntropyLoss()
        fine_optimizer = optim.AdamW(self.model.parameters(), lr=lr)

        total_loss = 0.0
        for _ in range(steps):
            fine_optimizer.zero_grad()
            pred_r, pred_b = self.model(x_tensor)
            loss_r = criterion_red(pred_r, y_r)
            loss_b = criterion_blue(pred_b, y_b)
            loss = loss_r * 2.0 + loss_b * 1.5
            loss.backward()
            fine_optimizer.step()
            total_loss += loss.item()

        self.save_model(self.model_path)
        return total_loss / steps

    def save_model(self, path: str):
        """Saves model weights."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(self.model.state_dict(), path)

    def load_model(self, path: str):
        """Loads model weights."""
        state_dict = torch.load(path, map_location=self.device, weights_only=True)
        self.model.load_state_dict(state_dict)
