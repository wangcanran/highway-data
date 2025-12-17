import os
from typing import List, Dict, Any

import pandas as pd

from gantry_rule_generator import generate_rule_based_gantry_transaction


BASE_DIR = os.path.dirname(__file__)
MODEL_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "models"))
OUT_CSV_RULE = os.path.join(MODEL_DIR, "gantry_rule_10000.csv")


def generate_gantry_rule_based(n: int) -> List[Dict[str, Any]]:
    """调用 gantry_rule_generator 中的规则生成函数，生成 n 条记录。"""
    records: List[Dict[str, Any]] = []
    for _ in range(n):
        rec = generate_rule_based_gantry_transaction()
        records.append(rec)
    return records


def main() -> None:
    os.makedirs(MODEL_DIR, exist_ok=True)

    num_samples = 10000
    print(f"[RULE] Generating {num_samples} rows using gantry_rule_generator ...")
    records = generate_gantry_rule_based(num_samples)

    df_rule = pd.DataFrame.from_records(records)
    df_rule.to_csv(OUT_CSV_RULE, index=False, encoding="utf-8-sig")
    print(f"[RULE] Saved to {OUT_CSV_RULE}, shape={df_rule.shape}")


if __name__ == "__main__":
    main()
