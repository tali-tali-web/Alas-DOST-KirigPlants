import torch
import torch.nn as nn
import torch.nn.functional as F



class StressTestCNN(nn.Module):

    def __init__(self):
        super().__init__()

        self.layers = nn.ModuleList([
            nn.Conv1d(1, 16, 5),
            nn.ReLU(),
            nn.MaxPool1d(2),

            nn.Conv1d(16, 32, 5),
            nn.ReLU(),
            nn.MaxPool1d(2),
        ])

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)