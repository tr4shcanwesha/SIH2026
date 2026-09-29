from pathlib import Path

import torch
import torch.nn as nn
from torchvision import models, transforms

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "honeychain_varroa_model.pth"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Recreate the exact architecture used during training
model = models.efficientnet_b0(weights=None)
model.classifier[1] = nn.Linear(
    model.classifier[1].in_features,
    2
)

checkpoint = torch.load(
    MODEL_PATH,
    map_location=device
)

model.load_state_dict(checkpoint["model_state_dict"])
model.to(device)
model.eval()

threshold = checkpoint["threshold"]

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])
def predict(image):
    image = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        outputs = model(image)
        probabilities = torch.softmax(outputs, dim=1)

    probability_infected = probabilities[0, 1].item()

    prediction = (
        "Infected"
        if probability_infected >= threshold
        else "Healthy"
    )

    return {
        "prediction": prediction,
        "probability_infected": probability_infected,
        "threshold": threshold
    }