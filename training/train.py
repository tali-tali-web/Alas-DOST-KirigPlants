import numpy as np
import pandas as pd
import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

WINDOW_SIZE = 128

def create_windows(values, label):
    X = []
    y = []

    for i in range(
        0,
        len(values) - WINDOW_SIZE,
        WINDOW_SIZE
    ):
        X.append(values[i:i + WINDOW_SIZE])
        y.append(label)

    return X, y


def load_class(csv_file, label):

    df = pd.read_csv(csv_file)

    values = df["value"].to_numpy()

    return create_windows(values, label)


def main():

    X = []
    y = []

    datasets = [
        ("./training/data/control.csv", 0),
        ("./training/data/stimulus.csv", 1),
    ]

    for csv_file, label in datasets:

        x_part, y_part = load_class(
            csv_file,
            label
        )

        X.extend(x_part)
        y.extend(y_part)

    X = np.array(X)
    y = np.array(y)

    print(f"Dataset shape: {X.shape}")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1
    )

    print("Training...")

    model.fit(
        X_train,
        y_train
    )

    predictions = model.predict(X_test)

    print("\nAccuracy:")
    print(
        accuracy_score(
            y_test,
            predictions
        )
    )

    print("\nClassification Report:")
    print(
        classification_report(
            y_test,
            predictions
        )
    )

    joblib.dump(
        model,
        "rf_model.joblib"
    )

    print("\nSaved rf_model.joblib")


if __name__ == "__main__":
    main()