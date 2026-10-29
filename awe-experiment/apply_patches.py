#!/usr/bin/env python3
"""
apply_patches.py:
Vá các lỗi kỹ thuật trong mã nguồn AWE:
1. Fix crash SQLiSessionResult: Không gọi .get() trên đối tượng không phải dict, tự động bóc tách FLAG{...}.
2. Thêm method scan() cho InfoDisclosureDetector.
3. Fix Fallback Rules: Khi attack surface = 0 (web CTF), cưỡng bức kích hoạt các module sqli, xss, command_injection.
4. Cải tiến XSS payload generator: bổ sung payload autofocus/onfocus để bypass blacklist.
5. Cập nhật Dockerfile XBEN-095-24 từ mysql:5.7.15 sang mysql:5.7.44.
"""

import os
import re
import sys

def patch_intelligent_orchestrator(base_dir):
    p = os.path.join(base_dir, "awe", "src", "orchestrators", "intelligent_orchestrator.py")
    if not os.path.exists(p):
        print(f"[ERR] File not found: {p}")
        return False

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    # 1. Vá dòng 833: Xử lý an toàn SQLiSessionResult
    old_line = "success = result if isinstance(result, bool) else result.get('success', False)"
    new_line = """
                if isinstance(result, bool):
                    success = result
                elif isinstance(result, dict):
                    success = result.get('success', False) or result.get('vulnerable', False)
                elif hasattr(result, 'vulnerable'):
                    success = bool(result.vulnerable)
                elif hasattr(result, 'success'):
                    success = bool(result.success)
                else:
                    success = False

                # Bóc tách cờ FLAG{...} nếu xuất hiện trong kết quả
                try:
                    res_str = str(result)
                    flags_captured = re.findall(r'FLAG\\{[a-zA-Z0-9_\\-]+\\}', res_str)
                    if flags_captured:
                        print(f"\\n  🚩 [FLAG PHÁT HIỆN]: {flags_captured[0]}")
                        success = True
                except Exception:
                    pass
"""
    if old_line in code:
        code = code.replace(old_line, new_line, 1)
        print("[OK] Đã vá lỗi SQLiSessionResult trong intelligent_orchestrator.py")
    else:
        print("[SKIP] Dòng SQLiSessionResult đã được vá hoặc khác cấu trúc")

    # 2. Vá Fallback Rules: Ép chạy xss, sqli, cmd_injection khi surface = 0
    fallback_target = "decision.reasoning = reasoning\n\n        # Estimate time and cost"
    fallback_replacement = """        # Fallback cho môi trường CTF Benchmark (khi crawler báo 0 form/parameter)
        if len(decision.priority_1) == 0 and len(decision.priority_2) == 0:
            if 'xss' not in self.skip_agents and XSS_AVAILABLE:
                decision.priority_1.append('xss')
                reasoning['xss'] = "CTF target with minimal surface: force testing XSS on endpoints"
            if 'sqli' not in self.skip_agents and SQLI_AVAILABLE:
                decision.priority_1.append('sqli')
                reasoning['sqli'] = "CTF target with minimal surface: force testing SQL injection"
            if 'command_injection' not in self.skip_agents and CMD_INJECTION_AVAILABLE:
                decision.priority_2.append('command_injection')
                reasoning['command_injection'] = "CTF target with minimal surface: testing command injection"

        decision.reasoning = reasoning

        # Estimate time and cost"""

    if fallback_target in code:
        code = code.replace(fallback_target, fallback_replacement, 1)
        print("[OK] Đã vá cơ chế Fallback Rules cho CTF trong intelligent_orchestrator.py")
    else:
        print("[SKIP] Fallback Rules đã được vá hoặc khác cấu trúc")

    with open(p, "w", encoding="utf-8") as f:
        f.write(code)

    return True

def patch_info_detector(base_dir):
    p = os.path.join(base_dir, "awe", "src", "info_disclosure_agent", "info_detector.py")
    if not os.path.exists(p):
        print(f"[ERR] File not found: {p}")
        return False

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    if "async def scan(" in code:
        print("[SKIP] InfoDisclosureDetector đã có method scan()")
        return True

    scan_method = """

    async def scan(self, target_url: str) -> dict:
        \"\"\"
        Asynchronously scan target URL and common endpoints for information disclosure and flags.
        \"\"\"
        import httpx
        endpoints = ["", "/secret.txt", "/flag.txt", "/.env", "/robots.txt", "/challenge", "/api"]
        base = target_url.rstrip('/')
        findings = []
        flag_found = None

        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            for ep in endpoints:
                url = base + ep
                try:
                    res = await client.get(url)
                    if res.status_code == 200:
                        flag = self.check_flag(res.text)
                        if flag:
                            flag_found = flag
                            findings.append(f"Flag found at {url}: {flag}")
                        disclosure = self.scan_response(res.text, dict(res.headers))
                        if disclosure.has_disclosures:
                            findings.append(f"Disclosures at {url}")
                except Exception:
                    pass

        is_vuln = len(findings) > 0 or (flag_found is not None)
        return {
            "vulnerable": is_vuln,
            "success": is_vuln,
            "flag": flag_found,
            "findings": findings
        }
"""
    code += scan_method
    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    print("[OK] Đã thêm method scan() vào InfoDisclosureDetector")
    return True

def patch_xss_payload_generator(base_dir):
    p = os.path.join(base_dir, "awe", "src", "xss_agent", "analyzers", "payload_generator.py")
    if not os.path.exists(p):
        print(f"[ERR] File not found: {p}")
        return False

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        code = f.read()

    # Bổ sung các payload bypass blacklist (autofocus onfocus)
    old_fallback = 'payload=f\'<svg onload="confirm({datetime.now().microsecond})">\''
    new_fallback = 'payload="<input autofocus onfocus=alert(1)>"'

    if old_fallback in code:
        code = code.replace(old_fallback, new_fallback)
        print("[OK] Đã cập nhật payload bypass autofocus trong payload_generator.py")
    else:
        print("[SKIP] Fallback payload đã cập nhật hoặc khác cấu trúc")

    with open(p, "w", encoding="utf-8") as f:
        f.write(code)
    return True

def patch_xben_095_dockerfile(base_dir):
    p = os.path.join(base_dir, "xbow-validation-benchmarks", "benchmarks", "xben-095-24", "src", "Dockerfile")
    if not os.path.exists(p):
        print(f"[INFO] Dockerfile XBEN-095-24 không tìm thấy tại {p}")
        return False

    with open(p, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    if "FROM mysql:5.7.15" in content:
        content = content.replace("FROM mysql:5.7.15", "FROM mysql:5.7.44")
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        print("[OK] Đã cập nhật base image XBEN-095-24 thành mysql:5.7.44")
    else:
        print("[SKIP] Dockerfile XBEN-095-24 đã cập nhật")
    return True

def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print("=== TIẾN HÀNH ÁP DỤNG CÁC BẢN VÁ KỸ THUẬT (PATCHES) ===")
    patch_intelligent_orchestrator(base_dir)
    patch_info_detector(base_dir)
    patch_xss_payload_generator(base_dir)
    patch_xben_095_dockerfile(base_dir)
    print("=== HOÀN TẤT ÁP DỤNG BẢN VÁ ===")

if __name__ == "__main__":
    main()
