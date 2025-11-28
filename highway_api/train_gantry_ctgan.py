"""\
使用 CTGAN 训练一个门架交易数据生成模型，并将模型保存到本地。

步骤：
1. 从数据库读取 gantrytransaction 表的真实数据；
2. 用 pandas DataFrame 承载；
3. 配置并训练 CTGAN 模型；
4. 将训练好的模型保存为 pickle 文件。
"""

import os
from typing import List, Optional

import pandas as pd
from sqlalchemy import func
from sdv.tabular import CTGAN
from sklearn.model_selection import train_test_split

from app import app, db
from models import GantryTransaction


# 纳入模型的字段列表（与规则生成的字段保持一致，可按需调整）
GANTRY_COLUMNS: List[str] = [
    # 1) 车辆与介质相关字段
    "vehicle_type",
    "media_type",
    "vehicle_sign",

    # 2) 时间相关
    "transaction_time",
    "entrance_time",

    # 3) 费用与里程
    "pay_fee",
    "discount_fee",
    "fee",
    "fee_mileage",

    # 4) 轴数与重量
    "axle_count",
    "total_weight",

    # 5) 状态/编码
    "gantry_type",
    "transaction_type",
    "pass_state",
    "entrance_lane_type",
    "cpu_card_type",
    "fee_prov_begin_hex",

    # 6) OBU 相关字段
    "obu_fee_sum_before",
    "obu_fee_sum_after",
    "pay_fee_prov_sum_local",

    # 7) 门架与路段信息
    "gantry_id",
    "section_id",
    "section_name",

    # 8) 主键与 pass_id
    "gantry_transaction_id",
    "pass_id",
]


def load_real_gantry_data(limit: Optional[int] = None) -> pd.DataFrame:
    """从数据库加载真实门架交易数据，并转为 pandas DataFrame。

    如果指定了 limit，则从全表随机抽样 limit 条记录；
    否则读取所有记录。train/test 划分在 pandas 层面完成。
    """
    session = db.session
    query = session.query(GantryTransaction)

    if limit is not None:
        # 随机顺序，再截取 limit 条，实现从全表随机抽样
        query = query.order_by(func.random()).limit(limit)

    rows = query.all()

    records: list[dict] = []
    for row in rows:
        rec = {}
        for col in GANTRY_COLUMNS:
            rec[col] = getattr(row, col)
        records.append(rec)

    df = pd.DataFrame.from_records(records)

    # 时间字段转字符串，方便 CTGAN 作为类别型处理
    for col in ["transaction_time", "entrance_time"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    return df


def train_ctgan(df: pd.DataFrame) -> CTGAN:
    """基于输入 DataFrame 训练一个 CTGAN 模型。"""

    model = CTGAN(
        epochs=50,      # 可按需要调整训练轮数
        batch_size=500,
        verbose=True,
    )

    model.fit(df)
    return model


def main() -> None:
    # 使用 Flask app_context 访问数据库
    with app.app_context():
        print("Loading real gantry data from DB...")
        # limit=None 表示读取所有真实数据，再在 pandas 层面划分 train/test
        df_all = load_real_gantry_data(limit=6000)

    print(f"Loaded {len(df_all)} rows, columns: {list(df_all.columns)}")

    # 在 pandas 层面划分训练集和测试集
    df_train, df_test = train_test_split(df_all, test_size=0.2, random_state=42)
    print(f"Train size: {len(df_train)}, Test size: {len(df_test)}")

    print("Training CTGAN model on train set...")
    model = train_ctgan(df_train)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # 保存模型
    model_path = os.path.join(out_dir, "gantry_ctgan.pkl")
    model.save(model_path)
    print(f"CTGAN model saved to {model_path}")

    # 保存测试集，供后续评估使用
    test_path = os.path.join(out_dir, "gantry_ctgan_testset.csv")
    df_test.to_csv(test_path, index=False)
    print(f"Test set saved to {test_path}")


if __name__ == "__main__":
    main()
