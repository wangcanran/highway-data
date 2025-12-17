"""
查看数据库中入口和出口交易记录的时间分布
"""
from app import app, db
from models import EntranceTransaction, ExitTransaction
from collections import Counter
from datetime import datetime

def check_entrance_distribution():
    """检查入口交易时间分布"""
    print("\n" + "="*60)
    print("  入口交易时间分布")
    print("="*60)
    
    with app.app_context():
        # 获取所有入口交易记录
        entrances = EntranceTransaction.query.all()
        print(f"\n总记录数: {len(entrances)}")
        
        if len(entrances) == 0:
            print("⚠️ 数据库中没有入口交易记录！")
            return
        
        # 统计日期分布
        date_counter = Counter()
        for record in entrances:
            if record.entrance_time:
                # entrance_time是datetime对象，需要转换为字符串
                if isinstance(record.entrance_time, str):
                    date = record.entrance_time[:10]
                else:
                    date = record.entrance_time.strftime('%Y-%m-%d')
                date_counter[date] += 1
        
        # 按日期排序显示
        print(f"\n按日期统计（共{len(date_counter)}个不同日期）：")
        print("-" * 60)
        for date in sorted(date_counter.keys()):
            count = date_counter[date]
            bar = "█" * min(50, count)
            print(f"{date}  {count:>5}条  {bar}")
        
        # 显示时间范围
        times = [r.entrance_time for r in entrances if r.entrance_time]
        if times:
            print(f"\n时间范围:")
            print(f"  最早: {min(times)}")
            print(f"  最晚: {max(times)}")

def check_exit_distribution():
    """检查出口交易时间分布"""
    print("\n" + "="*60)
    print("  出口交易时间分布")
    print("="*60)
    
    with app.app_context():
        # 获取所有出口交易记录
        exits = ExitTransaction.query.all()
        print(f"\n总记录数: {len(exits)}")
        
        if len(exits) == 0:
            print("⚠️ 数据库中没有出口交易记录！")
            return
        
        # 统计日期分布
        date_counter = Counter()
        for record in exits:
            if record.exit_time:
                # exit_time是datetime对象，需要转换为字符串
                if isinstance(record.exit_time, str):
                    date = record.exit_time[:10]
                else:
                    date = record.exit_time.strftime('%Y-%m-%d')
                date_counter[date] += 1
        
        # 按日期排序显示
        print(f"\n按日期统计（共{len(date_counter)}个不同日期）：")
        print("-" * 60)
        for date in sorted(date_counter.keys()):
            count = date_counter[date]
            bar = "█" * min(50, count)
            print(f"{date}  {count:>5}条  {bar}")
        
        # 显示时间范围
        times = [r.exit_time for r in exits if r.exit_time]
        if times:
            print(f"\n时间范围:")
            print(f"  最早: {min(times)}")
            print(f"  最晚: {max(times)}")

def check_section_distribution():
    """检查路段分布"""
    print("\n" + "="*60)
    print("  路段分布统计")
    print("="*60)
    
    with app.app_context():
        entrances = EntranceTransaction.query.all()
        
        section_counter = Counter()
        for record in entrances:
            if record.section_id:
                section_counter[f"{record.section_id} - {record.section_name}"] += 1
        
        print(f"\n按路段统计（共{len(section_counter)}个路段）：")
        print("-" * 60)
        for section, count in section_counter.most_common():
            bar = "█" * min(30, count // 10)
            print(f"{section:<50}  {count:>5}条  {bar}")

if __name__ == '__main__':
    print("\n" + "="*60)
    print("  高速公路数据时间分布分析")
    print("="*60)
    
    check_entrance_distribution()
    check_exit_distribution()
    check_section_distribution()
    
    print("\n" + "="*60)
    print("  分析完成")
    print("="*60)
