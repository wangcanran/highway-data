from collections import Counter

from flask import Flask

from app import app
from models import db, GantryTransaction, Gantry


def analyze_gantry_transaction(top_n: int = 20) -> None:
    """简单分析 gantrytransaction 表部分字段的取值范围和分布。

    - 数值/时间字段: 统计 min/max
    - 枚举/状态字段: 统计不同取值和出现次数 (前 top_n 个 + 全量枚举)
    """
    with app.app_context():
        session = db.session

        # 同时输出到控制台和文本文件，方便后续查看和做规则
        lines: list[str] = []

        def log(msg: str) -> None:
            print(msg)
            lines.append(msg)

        total = session.query(GantryTransaction).count()
        log(f"总记录数: {total}")

        # 1) 数值/时间字段的 min/max
        numeric_time_fields = [
            GantryTransaction.transaction_time,
            GantryTransaction.entrance_time,
            GantryTransaction.pay_fee,
            GantryTransaction.discount_fee,
            GantryTransaction.fee_mileage,
            GantryTransaction.obu_fee_sum_before,
            GantryTransaction.obu_fee_sum_after,
            GantryTransaction.pay_fee_prov_sum_local,
        ]

        log("\n=== 数值/时间字段 min/max ===")
        for col in numeric_time_fields:
            name = col.key
            q_min = session.query(col).order_by(col.asc()).limit(1).scalar()
            q_max = session.query(col).order_by(col.desc()).limit(1).scalar()
            log(f"{name}: min = {q_min}, max = {q_max}")

        # 2) 枚举/状态型字段: distinct 值及频次 (不限制数量，全部输出)
        category_fields = [
            GantryTransaction.gantry_type,
            GantryTransaction.media_type,
            GantryTransaction.vehicle_type,
            GantryTransaction.vehicle_sign,
            GantryTransaction.transaction_type,
            GantryTransaction.pass_state,
            GantryTransaction.entrance_lane_type,
            GantryTransaction.axle_count,
            GantryTransaction.cpu_card_type,
            GantryTransaction.fee_prov_begin_hex,
            GantryTransaction.total_weight,
            GantryTransaction.fee,
            GantryTransaction.section_name,
        ]

        log("\n=== 枚举/状态字段取值分布 (全部取值) ===")
        for col in category_fields:
            name = col.key
            values = session.query(col).all()
            cnt = Counter(v[0] for v in values if v[0] is not None)
            log(f"\n字段 {name}: 不同取值个数 = {len(cnt)}")
            # 全量输出: 按出现次数从高到低排序
            for val, c in cnt.most_common():
                log(f"  {repr(val)}: {c}")

        # 3) 其他关心的键值分布: gantry_id / section_id (同样全部输出)
        extra_fields = [
            GantryTransaction.gantry_id,
            GantryTransaction.section_id,
        ]

        for col in extra_fields:
            name = col.key
            values = session.query(col).all()
            cnt = Counter(v[0] for v in values if v[0] is not None)
            log(f"\n字段 {name}: 不同取值个数 = {len(cnt)} (全部输出)")
            for val, c in cnt.most_common():
                log(f"  {repr(val)}: {c}")

        # 4) Gantry 表中 gantry_id 与 section_id 的对应关系
        log("\n=== Gantry 表中 gantry_id 与 section_id 对应关系检查 ===")
        gantries = session.query(Gantry.gantry_id, Gantry.section_id).all()
        mapping: dict[str, set[str]] = {}
        for gid, sid in gantries:
            if gid is None:
                continue
            if gid not in mapping:
                mapping[gid] = set()
            if sid is not None:
                mapping[gid].add(sid)

        log(f"总门架数量: {len(mapping)}")
        multi_section = {gid: sids for gid, sids in mapping.items() if len(sids) > 1}
        if not multi_section:
            log("所有 gantry_id 仅关联到一个 section_id (一对一关系)")
        else:
            log("存在同时属于多个 section_id 的门架:")
            for gid, sids in multi_section.items():
                log(f"  gantry_id={gid}, section_ids={sorted(sids)}")

        # 打印完整的 gantry_id -> section_id 映射，按 section_id、gantry_id 排序
        log("\nGantry 表完整映射 (gantry_id -> section_id):")
        for gid, sids in sorted(mapping.items(), key=lambda x: (sorted(x[1])[0] if x[1] else "", x[0])):
            sid_list = sorted(sids) if sids else ["<None>"]
            # 一对一关系下这里通常只有一个元素
            log(f"  {gid} -> {sid_list[0]}")

        # 将所有日志写入本地 txt 文件，便于后续人工查看和使用
        output_path = "gantry_value_analysis.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        print(f"\n分析结果已写入 {output_path}")


if __name__ == "__main__":
    analyze_gantry_transaction(top_n=30)
