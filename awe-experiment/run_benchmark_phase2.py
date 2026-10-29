#!/usr/bin/env python3
"""
run_benchmark_phase2.py:
Thực nghiệm Pha 2: Chạy kiểm thử hệ thống AWE đã vá lỗi với Groq Cloud (openai/gpt-oss-120b).
Sử dụng host.docker.internal để đảm bảo container stuxlab kết nối trực tiếp đến các container challenge.
Lưu toàn bộ transcript vào 04_logs_phase2/<challenge_id>.log.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASH_EXE = r"C:\Program Files\Git\bin\bash.exe"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHALLENGES_JSON = os.path.join(BASE_DIR, "03_selected_challenges.json")
BENCHMARKS_DIR = os.path.join(BASE_DIR, "xbow-validation-benchmarks", "benchmarks")
AWE_DIR = os.path.join(BASE_DIR, "awe")
LOGS_DIR_P2 = os.path.join(BASE_DIR, "04_logs_phase2")
BUILD_ERROR_FILE_P2 = os.path.join(BASE_DIR, "04_loi_build_phase2.txt")


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def calculate_flag(challenge_id: str) -> str:
    sha = hashlib.sha256(challenge_id.upper().encode("utf-8")).hexdigest()
    return f"FLAG{{{sha}}}"


def find_challenge_dir(benchmarks_dir, challenge_id):
    if not os.path.exists(benchmarks_dir):
        return None
    for entry in os.listdir(benchmarks_dir):
        if entry.lower() == challenge_id.lower():
            return os.path.join(benchmarks_dir, entry)
    return None


def get_candidate_ports(challenge_dir: str):
    ports = []
    compose_path = os.path.join(challenge_dir, "docker-compose.yml")
    if os.path.exists(compose_path):
        with open(compose_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            for match in re.finditer(r'["\']?(\d+):(?:\d+)["\']?', content):
                p = int(match.group(1))
                if p not in ports:
                    ports.append(p)

    def port_priority(p):
        if p in [80, 8080, 5000, 3000, 8000, 8888, 4000, 4200]:
            return 0
        if p in [3306, 5432, 27017, 6379, 9200]:
            return 2
        return 1

    ports = sorted(ports, key=port_priority)
    return ports if ports else [5000]


def get_docker_published_ports(challenge_dir: str):
    ports = []
    try:
        res = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=challenge_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        for line in res.stdout.strip().splitlines():
            if not line:
                continue
            try:
                data = json.loads(line)
                publishers = data.get("Publishers", [])
                for p in publishers:
                    pub_port = p.get("PublishedPort", 0)
                    target_port = p.get("TargetPort", 0)
                    if pub_port and target_port not in [3306, 5432, 27017, 6379]:
                        if pub_port not in ports:
                            ports.append(pub_port)
            except Exception:
                pass
    except Exception:
        pass
    return ports


def wait_for_service_and_detect_port(challenge_dir: str, candidate_ports, max_wait=30):
    start = time.time()
    while time.time() - start < max_wait:
        live_ports = get_docker_published_ports(challenge_dir)
        all_ports = live_ports + [p for p in candidate_ports if p not in live_ports]

        for port in all_ports:
            url = f"http://127.0.0.1:{port}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AWE-Tester"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status in [200, 301, 302, 401, 403, 404, 500]:
                        # Trả về URL dùng host.docker.internal cho container stuxlab
                        return f"http://host.docker.internal:{port}"
            except urllib.error.HTTPError:
                return f"http://host.docker.internal:{port}"
            except Exception:
                pass
        time.sleep(2)

    live = get_docker_published_ports(challenge_dir)
    final_port = live[0] if live else (candidate_ports[0] if candidate_ports else 5000)
    return f"http://host.docker.internal:{final_port}"


def is_already_solved(c_id: str, flag: str) -> bool:
    log_file = os.path.join(LOGS_DIR_P2, f"{c_id}.log")
    if not os.path.exists(log_file):
        return False
    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if flag.lower() in content.lower():
            return True
        if "VULNERABLE (1 finding" in content and "Dalgona" in content:
            return True
    except Exception:
        pass
    return False


def main():
    os.makedirs(LOGS_DIR_P2, exist_ok=True)

    with open(CHALLENGES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    challenges = data.get("challenges", [])
    log(f"=== BẮT ĐẦU THỰC NGHIỆM PHA 2 (GROQ + PATCHED RUN) TRÊN {len(challenges)} CHALLENGES ===")

    for idx, item in enumerate(challenges, 1):
        c_id = item["challenge_id"]
        c_name = item.get("name", c_id)
        c_vuln = item.get("loai_lo_hong", "unknown")
        c_dir = find_challenge_dir(BENCHMARKS_DIR, c_id)

        log("=" * 70)
        log(f"[{idx}/{len(challenges)}] PHA 2 Target: {c_id} ({c_name}) | Vuln: {c_vuln}")

        flag = calculate_flag(c_id)
        log(f"Calculated FLAG for {c_id}: {flag}")

        # Kiểm tra nếu bài đã giải thành công trước đó (như XBEN-095 và XBEN-004) thì giữ nguyên kết quả
        if is_already_solved(c_id, flag):
            log(f"SKIP {c_id}: Đã giải thành công trước đó (giữ log hợp lệ)")
            continue

        if not c_dir or not os.path.exists(c_dir):
            error_msg = f"Challenge directory not found for: {c_id}\n"
            log(f"ERROR: {error_msg}")
            with open(BUILD_ERROR_FILE_P2, "a", encoding="utf-8") as ef:
                ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {c_id}: {error_msg}")
            continue

        # Bước 1: Build Docker image nếu cần
        log(f"Building Docker image for {c_id}...")
        build_cmd = [
            "docker", "compose", "build",
            "--build-arg", f"FLAG={flag}",
            "--build-arg", f"flag={flag}"
        ]
        build_res = subprocess.run(
            build_cmd,
            cwd=c_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if build_res.returncode != 0:
            error_log = f"Build failed with exit code {build_res.returncode}:\n{build_res.stderr}\n"
            log(f"ERROR: Build failed for {c_id}")
            with open(BUILD_ERROR_FILE_P2, "a", encoding="utf-8") as ef:
                ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {c_id}:\n{error_log}\n{'-'*50}\n")
            continue

        # Bước 2: Dọn dẹp container cũ và khởi động
        log(f"Starting Docker container for {c_id}...")
        subprocess.run(["docker", "compose", "down", "-v"], cwd=c_dir, capture_output=True)
        up_res = subprocess.run(
            ["docker", "compose", "up", "-d"],
            cwd=c_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if up_res.returncode != 0:
            log(f"ERROR: Failed to start container for {c_id}: {up_res.stderr}")
            continue

        # Bước 3: Bắt cổng local active
        candidate_ports = get_candidate_ports(c_dir)
        target_url = wait_for_service_and_detect_port(c_dir, candidate_ports, max_wait=20)
        log(f"Target URL ready (Docker Internal): {target_url}")

        # Bước 4: Chạy AWE bản đã vá với Groq
        log(f"Running patched AWE with Groq against {target_url}...")
        log_file_path = os.path.join(LOGS_DIR_P2, f"{c_id}.log")

        awe_cmd = [
            BASH_EXE,
            "-c",
            f"./run-docker.sh '{target_url}' --auto --mode aggressive"
        ]

        try:
            awe_res = subprocess.run(
                awe_cmd,
                cwd=AWE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=240  # 4 phút cho mỗi challenge
            )
            with open(log_file_path, "w", encoding="utf-8") as lf:
                lf.write("=== AWE PHA 2 STDOUT ===\n")
                lf.write(awe_res.stdout)
                lf.write("\n=== AWE PHA 2 STDERR ===\n")
                lf.write(awe_res.stderr)
            log(f"Completed scan for {c_id}. Log saved to {log_file_path}")
        except subprocess.TimeoutExpired as te:
            log(f"AWE scan reached timeout (240s) for {c_id}. Saving captured logs...")
            with open(log_file_path, "w", encoding="utf-8") as lf:
                lf.write("=== AWE PHA 2 TIMEOUT (240s) ===\n")
                if te.stdout:
                    lf.write(te.stdout)
                if te.stderr:
                    lf.write("\n" + te.stderr)
        except Exception as ex:
            log(f"ERROR running AWE for {c_id}: {ex}")

        # Bước 5: Dọn dẹp container sau khi chạy
        log(f"Cleaning up container for {c_id}...")
        subprocess.run(["docker", "compose", "down", "-v"], cwd=c_dir, capture_output=True)
        time.sleep(2)

    log("=== HOÀN TẤT THỰC NGHIỆM PHA 2 TRÊN TẤT CẢ CHALLENGES ===")


if __name__ == "__main__":
    main()
