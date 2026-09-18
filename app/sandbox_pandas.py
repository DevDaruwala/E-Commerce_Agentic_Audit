import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

df = pd.read_csv(BASE_DIR / "data" / "classifier_training_data.csv")

print(df.head())
print(df.info())
print(df["is_unsafe"].value_counts())
print(df["category"].value_counts())