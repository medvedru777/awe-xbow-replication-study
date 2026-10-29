import csv
import json
import os
import random

SEED = 42
SAMPLE_SIZE = 12

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(base_dir, "02_danh_sach_challenge.csv")
    output_path = os.path.join(base_dir, "03_selected_challenges.json")

    # Read all challenges from CSV
    challenges = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            challenges.append(row)

    print(f"Total challenges loaded: {len(challenges)}")

    # Sort challenges deterministically before sampling to ensure 100% reproducibility
    challenges = sorted(challenges, key=lambda x: x["challenge_id"])

    # Set random seed
    random.seed(SEED)

    # Randomly sample 12 challenges
    selected = random.sample(challenges, SAMPLE_SIZE)

    # Sort selected challenges deterministically by ID for clear presentation
    selected = sorted(selected, key=lambda x: x["challenge_id"])

    # Analyze vulnerability coverage
    vuln_types = set()
    for item in selected:
        vuln_types.add(item.get("loai_lo_hong", "unknown"))

    print(f"Selected {len(selected)} challenges with seed {SEED}")
    print(f"Vulnerability types covered ({len(vuln_types)}): {sorted(list(vuln_types))}")

    # Verify requirement: at least 3 vulnerability types
    assert len(vuln_types) >= 3, f"Requirement failed: only {len(vuln_types)} vulnerability types covered"

    result = {
        "seed": SEED,
        "sample_size": SAMPLE_SIZE,
        "vulnerability_types_count": len(vuln_types),
        "vulnerability_types": sorted(list(vuln_types)),
        "challenges": selected
    }

    with open(output_path, mode="w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved to {output_path}")

if __name__ == "__main__":
    main()
