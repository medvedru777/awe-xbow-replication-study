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
LOGS_DIR = os.path.join(BASE_DIR, "04_logs")
BUILD_ERROR_FILE = os.path.join(BASE_DIR, "04_loi_build.txt")


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def calculate_flag(challenge_id: str) -> str:
    sha = hashlib.sha256(challenge_id.upper().encode("utf-8")).hexdigest()
    return f"FLAG{{{sha}}}"


def get_candidate_ports(challenge_dir: str):
    """Find all candidate ports from docker-compose.yml"""
    ports = []
    compose_path = os.path.join(challenge_dir, "docker-compose.yml")
    if os.path.exists(compose_path):
        with open(compose_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Match ports like "5000:5000" or "80:80"
            for match in re.finditer(r'["\']?(\d+):(?:\d+)["\']?', content):
                p = int(match.group(1))
                if p not in ports:
                    ports.append(p)

    # Sort so likely HTTP ports come first, and DB ports come last
    def port_priority(p):
        if p in [80, 8080, 5000, 3000, 8000, 8888, 4000, 4200]:
            return 0
        if p in [3306, 5432, 27017, 6379, 9200]:
            return 2
        return 1

    ports = sorted(ports, key=port_priority)
    return ports if ports else [5000]


def get_docker_published_ports(challenge_dir: str):
    """Find all dynamically published ports from running docker containers"""
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
    """Probe candidate and published ports, returning the active HTTP target URL"""
    start = time.time()
    while time.time() - start < max_wait:
        # Check published ports first
        live_ports = get_docker_published_ports(challenge_dir)
        all_ports = live_ports + [p for p in candidate_ports if p not in live_ports]

        for port in all_ports:
            url = f"http://127.0.0.1:{port}"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AWE-Tester"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status in [200, 301, 302, 401, 403, 404, 500]:
                        return url
            except urllib.error.HTTPError:
                return url
            except Exception:
                pass
        time.sleep(2)

    live = get_docker_published_ports(challenge_dir)
    final_port = live[0] if live else (candidate_ports[0] if candidate_ports else 5000)
    return f"http://127.0.0.1:{final_port}"


def main():
    os.makedirs(LOGS_DIR, exist_ok=True)

    with open(CHALLENGES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    challenges = data.get("challenges", [])
    log(f"Loaded {len(challenges)} challenges to test from {CHALLENGES_JSON}")

    for idx, item in enumerate(challenges, 1):
        c_id = item["challenge_id"]
        c_name = item.get("name", c_id)
        c_vuln = item.get("loai_lo_hong", "unknown")
        c_dir = os.path.join(BENCHMARKS_DIR, c_id)

        log("=" * 70)
        log(f"[{idx}/{len(challenges)}] Starting challenge: {c_id} ({c_name}) | Vuln: {c_vuln}")

        if not os.path.exists(c_dir):
            error_msg = f"Challenge directory not found: {c_dir}\n"
            log(f"ERROR: {error_msg}")
            with open(BUILD_ERROR_FILE, "a", encoding="utf-8") as ef:
                ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {c_id}: {error_msg}")
            continue

        flag = calculate_flag(c_id)
        log(f"Target Flag: {flag}")

        # 1. Build challenge
        log(f"Building Docker image for {c_id}...")
        build_cmd = [
            "docker", "compose", "build",
            "--build-arg", f"FLAG={flag}",
            "--build-arg", f"flag={flag}"
        ]
        build_res = subprocess.run(build_cmd, cwd=c_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if build_res.returncode != 0:
            err_reason = f"Build failed with exit code {build_res.returncode}:\n{build_res.stderr[-2000:]}\n"
            log(f"FAIL BUILD: {c_id}")
            with open(BUILD_ERROR_FILE, "a", encoding="utf-8") as ef:
                ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {c_id}:\n{err_reason}\n" + "-" * 50 + "\n")
            continue

        # 2. Run challenge container
        log(f"Starting container for {c_id}...")
        up_cmd = ["docker", "compose", "up", "-d"]
        up_res = subprocess.run(up_cmd, cwd=c_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if up_res.returncode != 0:
            err_reason = f"Compose up failed with exit code {up_res.returncode}:\n{up_res.stderr[-2000:]}\n"
            log(f"FAIL UP: {c_id}")
            with open(BUILD_ERROR_FILE, "a", encoding="utf-8") as ef:
                ef.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {c_id} compose up:\n{err_reason}\n" + "-" * 50 + "\n")
            continue

        candidate_ports = get_candidate_ports(c_dir)
        log(f"Candidate ports: {candidate_ports}")
        log("Waiting for web service to respond and detecting HTTP port...")
        target_url = wait_for_service_and_detect_port(c_dir, candidate_ports, max_wait=20)
        log(f"Active target URL identified: {target_url}")

        # 3. Run AWE against target
        log(f"Launching AWE against {target_url} (intelligent orchestration --auto --mode aggressive)...")
        awe_log_file = os.path.join(LOGS_DIR, f"{c_id}.log")

        start_time = time.time()
        awe_cmd = [
            BASH_EXE,
            "-c",
            f"./run-docker.sh '{target_url}' --auto --mode aggressive"
        ]

        try:
            awe_process = subprocess.run(
                awe_cmd,
                cwd=AWE_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600  # 10 min timeout as per paper
            )
            elapsed = time.time() - start_time
            log(f"AWE finished in {elapsed:.1f} seconds with exit code {awe_process.returncode}")

            raw_output = f"=== AWE STDOUT ===\n{awe_process.stdout}\n\n=== AWE STDERR ===\n{awe_process.stderr}\n"

        except subprocess.TimeoutExpired as te:
            elapsed = time.time() - start_time
            log(f"AWE TIMED OUT after {elapsed:.1f} seconds")
            raw_output = f"=== AWE TIMEOUT EXPIRED (600s) ===\n{te.stdout or ''}\n{te.stderr or ''}\n"

        except Exception as e:
            elapsed = time.time() - start_time
            log(f"AWE error: {e}")
            raw_output = f"=== AWE EXECUTION ERROR ===\n{str(e)}\n"

        # Save raw log file
        with open(awe_log_file, "w", encoding="utf-8", errors="ignore") as lf:
            lf.write(raw_output)
        log(f"Saved complete log to {awe_log_file}")

        # 4. Teardown target
        log(f"Stopping and cleaning up container for {c_id}...")
        down_cmd = ["docker", "compose", "down", "-v"]
        subprocess.run(down_cmd, cwd=c_dir, capture_output=True, text=True, encoding="utf-8", errors="replace")
        time.sleep(2)

    log("=" * 70)
    log("All 12 challenges processed! Step 4 complete.")


if __name__ == "__main__":
    main()
