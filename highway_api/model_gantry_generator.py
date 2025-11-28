import os
from typing import List, Dict, Optional

import pandas as pd
from sdv.tabular import CTGAN


# 训练脚本保存的 CTGAN 模型路径
MODEL_PATH = r"D:\python_code\flaskProject\models\gantry_ctgan.pkl"

_model_cache: Optional[CTGAN] = None


def load_gantry_ctgan() -> CTGAN:
    """加载训练好的 CTGAN 模型（带简单缓存）。"""
    global _model_cache
    if _model_cache is not None:
        return _model_cache

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"CTGAN model file not found: {MODEL_PATH}")

    model = CTGAN.load(MODEL_PATH)
    _model_cache = model
    return model


def generate_model_based_gantry(n: int = 10) -> List[Dict]:
    """使用训练好的 CTGAN 模型生成 n 条门架交易记录。

    返回值为 list[dict]，方便在脚本或 Flask API 中直接返回 JSON。
    """
    model = load_gantry_ctgan()
    df_fake: pd.DataFrame = model.sample(n)
    return df_fake.to_dict(orient="records")
