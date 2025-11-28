from collections import Counter, defaultdict

from app import db, app
from models import GantryTransaction


def analyze_vehicle_axle_joint_distribution(output_path: str = "gantry_vehicle_axle_joint.txt") -> None:
    """统计 vehicle_type 与 axle_count 的联合频数，并写入文本文件。

    输出格式示例：
    total_records: 43169
    vehicle_type,axle_count,count
    1,2.0,XXXXX
    1,3.0,YYYYY
    ...
    """
    session = db.session

    q = (
        session.query(
            GantryTransaction.vehicle_type,
            GantryTransaction.axle_count,
        )
    )

    joint_counter: Counter[tuple[str, str]] = Counter()
    vt_counter: Counter[str] = Counter()

    for vt, axle in q:
        if vt is None or axle is None:
            continue
        vt = str(vt)
        axle = str(axle)
        joint_counter[(vt, axle)] += 1
        vt_counter[vt] += 1

    total = sum(joint_counter.values())

    lines: list[str] = []
    lines.append(f"total_records: {total}\n")
    lines.append("vehicle_type,axle_count,count\n")

    # 为了可读性，先按 vehicle_type 分组，再按 count 降序
    by_vt: defaultdict[str, list[tuple[str, int]]] = defaultdict(list)
    for (vt, axle), c in joint_counter.items():
        by_vt[vt].append((axle, c))

    for vt in sorted(by_vt.keys(), key=lambda x: (len(x), x)):
        pairs = sorted(by_vt[vt], key=lambda x: -x[1])
        for axle, c in pairs:
            lines.append(f"{vt},{axle},{c}\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"Joint distribution written to {output_path}")


if __name__ == "__main__":
    with app.app_context():
        analyze_vehicle_axle_joint_distribution()
