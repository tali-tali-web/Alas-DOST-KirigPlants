
import numpy as np

import torch
import torch.nn as nn
import torch.nn.functional as F
class PlantCNN(nn.Module):

    def __init__(self):
        super().__init__()

        # Feature extraction
        self.conv1 = nn.Conv1d(
            in_channels=1,
            out_channels=16,
            kernel_size=5
        )

        self.pool = nn.MaxPool1d(2)

        # Classifier
        self.fc1 = nn.Linear(16 * 62, 64)
        self.fc2 = nn.Linear(64, 2)

    def forward(self, x):

        # x: (batch, 1, 128)

        x = self.conv1(x)

        x = F.relu(x)

        x = self.pool(x)

        # (batch, 16, 62)

        x = torch.flatten(x, 1)

        # (batch, 992)

        x = self.fc1(x)

        x = F.relu(x)

        x = self.fc2(x)

        # (batch, 2)

        return x

test = PlantCNN()

async def receive_data(window : list):
    global test

    window = np.array(window)

    normalized_window = torch.from_numpy((window - window.mean()) / max(window.std(), 1e-8))

    result = test(normalized_window.float().unsqueeze(0).unsqueeze(0))

    print(result)

    return result



    