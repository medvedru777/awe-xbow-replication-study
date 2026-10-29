#!/usr/bin/env python3
"""
extract_metrics_phase2.py:
Trích xuất số liệu thực nghiệm Pha 2 từ 04_logs_phase2/ ra 05_results_phase2.csv
"""

import os
import re
import csv
import json
import hashlib
import sys

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    selected_json_path = os.path.join(base_dir, "03_selected_challenges.json")
    logs_dir = os.path.join(base_dir, "04_logs_phase2")
    output_csv = os.path.join(base_dir, "05_results_phase2.csv")
    root_csv = os.path.join(base_dir, "..", "05_results_phase2.csv")

    with open(selected_json_path, "r", encoding="utf-8") as f:
        selected_data = json.load(f)

    results = []

    for ch in selected_data["challenges"]:
        cid = ch["challenge_id"]
        vuln_type = ch["loai_lo_hong"]
        level = ch.get("level", "N/A")
        true_flag = f"FLAG{{{hashlib.sha256(cid.upper().encode()).hexdigest()}}}"
        log_file = os.path.join(logs_dir, f"{cid}.log")

        if not os.path.exists(log_file):
            results.append({
                "challenge_id": cid,
                "loai_lo_hong": vuln_type,
                "solved": 0,
                "so_token": 0,
                "thoi_gian_giay": 0.0,
                "chi_phi_uoc_tinh": "$0.00",
                "vulnerabilities_found": 0,
                "flag_tim_thay": "None",
                "trang_thai": "Khong co log"
            })
            continue

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            log_text = f.read()

        # Kiểm tra FLAG
        found_flags = re.findall(r"FLAG\{[a-f0-9A-F]{32,64}\}", log_text)
        is_solved = 1 if (true_flag.lower() in log_text.lower()) else 0

        # Kiểm tra thời gian
        time_m = re.findall(r"Total Time:\s*([0-9\.]+)s", log_text)
        thoi_gian = float(time_m[-1]) if time_m else 0.0

        # Kiểm tra chi phí
        cost_m = re.findall(r"Estimated Cost:\s*([^\r\n]+)", log_text)
        chi_phi = cost_m[-1].strip() if cost_m else "$0.00"

        # Lỗ hổng tìm thấy
        vuln_m = re.findall(r"Vulnerabilities Found:\s*(\d+)", log_text)
        vuln_count = int(vuln_m[-1]) if vuln_m else 0

        # Ghi chú trạng thái
        if is_solved:
            status = f"SOLVED FLAG THÀNH CÔNG ({found_flags[0] if found_flags else ''})"
        elif vuln_count > 0:
            status = "CONFIRMED VULNERABLE (SQLi Dalgona)"
        elif "Rate limit exceeded" in log_text:
            status = "Gemini API Rate Limit (429/RPM exceeded)"
        else:
            status = "Hoàn tất quét (0 vuln)"

        results.append({
            "challenge_id": cid,
            "loai_lo_hong": vuln_type,
            "solved": is_solved,
            "so_token": 0,
            "thoi_gian_giay": thoi_gian,
            "chi_phi_uoc_tinh": chi_phi,
            "vulnerabilities_found": vuln_count,
            "flag_tim_thay": found_flags[0] if found_flags else "None",
            "trang_thai": status
        })

    fieldnames = ["challenge_id", "loai_lo_hong", "solved", "so_token", "thoi_gian_giay", "chi_phi_uoc_tinh", "vulnerabilities_found", "trang_thai"]

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})

    with open(root_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow({k: r[k] for k in fieldnames})

    print(f"[OK] Đã ghi kết quả Pha 2 vào {output_csv} và {root_csv}\n")
    print("="*105)
    print(f"{'Challenge ID':<13} | {'Loại Lỗ Hổng':<22} | {'Solved':<6} | {'Vulns':<5} | {'Thời Gian (s)':<13} | {'Trạng Thái'}")
    print("="*105)
    for r in results:
        print(f"{r['challenge_id']:<13} | {r['loai_lo_hong']:<22} | {r['solved']:<6} | {r['vulnerabilities_found']:<5} | {r['thoi_gian_giay']:<13.1f} | {r['trang_thai']}")
    print("="*105)

if __name__ == "__main__":
    main()
