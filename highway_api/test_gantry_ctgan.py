"""测试基于 CTGAN 模型的门架交易数据生成效果"""
import sys
from pprint import pprint

from model_gantry_generator import generate_model_based_gantry


def main() -> None:
    n = 5  # 生成条数，可按需修改
    print(f"=== MODEL BASED (CTGAN) GANTRY TRANSACTIONS, n={n} ===")

    rows = generate_model_based_gantry(20)
    for i, r in enumerate(rows, 1):
        print(f"\n----- ROW {i} -----")
        pprint(r, sort_dicts=False)


if __name__ == "__main__":
    # 确保脚本从项目根目录执行：python highway_api\\test_gantry_ctgan.py
    if r"D:\\python_code\\flaskProject" not in sys.path:
        sys.path.append(r"D:\\python_code\\flaskProject")
    main()
