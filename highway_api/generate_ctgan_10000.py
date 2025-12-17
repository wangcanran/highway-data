import os
import pandas as pd
from sdv.tabular import CTGAN

BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "models"))
MODEL_PATH = os.path.join(MODEL_DIR, "gantry_ctgan.pkl")
OUT_CSV_CTGAN = os.path.join(MODEL_DIR, "gantry_ctgan_10000.csv")


def main():
    os.makedirs(MODEL_DIR, exist_ok=True)
    print(f"[CTGAN] Loading model from {MODEL_PATH} ...")
    model = CTGAN.load(MODEL_PATH)

    num_samples = 10000
    print(f"[CTGAN] Sampling {num_samples} rows ...")
    df_fake = model.sample(num_samples)
    df_fake.to_csv(OUT_CSV_CTGAN, index=False, encoding="utf-8-sig")
    print(f"[CTGAN] Saved to {OUT_CSV_CTGAN}, shape={df_fake.shape}")

if __name__ == "__main__":
    main()
