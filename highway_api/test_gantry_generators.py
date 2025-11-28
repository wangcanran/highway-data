from gantry_rule_generator import generate_rule_based_gantry_transaction
from gantry_stat_generator import generate_statistical_gantry_transaction


def main() -> None:
    print("=== RULE BASED ===")
    for i in range(3):
        rec = generate_rule_based_gantry_transaction()
        print(f"RULE {i + 1}:", rec)

    print("\n=== STAT BASED ===")
    for i in range(3):
        rec = generate_statistical_gantry_transaction()
        print(f"STAT {i + 1}:", rec)


if __name__ == "__main__":
    main()
