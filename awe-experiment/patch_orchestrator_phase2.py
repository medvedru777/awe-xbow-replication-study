import re

path = r"awe-experiment/awe/src/orchestrators/intelligent_orchestrator.py"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

# 1. Patch test_ssti
old_ssti = """    async def test_ssti(url):
        orchestrator = ContextAwareSSTIOrchestrator()
        result = await orchestrator.test_parameter(url, None, None)
        return result.get('vulnerable', False) if result else False"""

new_ssti = """    async def test_ssti(url):
        try:
            from src.xss_agent.llm_client import get_llm_client
            llm = get_llm_client()
            orchestrator = ContextAwareSSTIOrchestrator(llm_client=llm)
            result = await orchestrator.test_parameter("q", None, None)
            return result.vulnerable if hasattr(result, 'vulnerable') else False
        except Exception:
            return False"""

# Normalize CRLF
text = text.replace("\r\n", "\n")
old_ssti = old_ssti.replace("\r\n", "\n")
if old_ssti in text:
    text = text.replace(old_ssti, new_ssti)
    print("Patched test_ssti")
else:
    print("test_ssti not matched directly")

# 2. Patch test_default_credentials
old_creds = """    async def test_default_credentials(url, max_passwords=100):
        tester = CredentialTester()
        result = await tester.test_url(url, max_passwords=max_passwords)
        return result.get('success', False) if result else False"""

new_creds = """    async def test_default_credentials(url, max_passwords=100):
        try:
            tester = CredentialTester()
            if hasattr(tester, 'test_url'):
                result = await tester.test_url(url, max_passwords=max_passwords)
                return result.get('success', False) if isinstance(result, dict) else False
            return False
        except Exception:
            return False"""

old_creds = old_creds.replace("\r\n", "\n")
if old_creds in text:
    text = text.replace(old_creds, new_creds)
    print("Patched test_default_credentials")
else:
    print("test_default_credentials not matched directly")

# 3. Patch CTF mode in _llm_agent_decision
old_decision = """            decision = AgentDecision(
                priority_1=decision_data.get('priority_1', []),
                priority_2=decision_data.get('priority_2', []),
                priority_3=decision_data.get('priority_3', []),
                skip=decision_data.get('skip', []),
                reasoning=decision_data.get('reasoning', {}),
                estimated_time_minutes=decision_data.get('estimated_time_minutes', '3-5'),
                estimated_cost_usd=decision_data.get('estimated_cost_usd', '$0.50-1.00'),
                confidence_score=decision_data.get('confidence_score', 0.8)
            )

            return decision"""

new_decision = """            decision = AgentDecision(
                priority_1=decision_data.get('priority_1', []),
                priority_2=decision_data.get('priority_2', []),
                priority_3=decision_data.get('priority_3', []),
                skip=decision_data.get('skip', []),
                reasoning=decision_data.get('reasoning', {}),
                estimated_time_minutes=decision_data.get('estimated_time_minutes', '3-5'),
                estimated_cost_usd=decision_data.get('estimated_cost_usd', '$0.50-1.00'),
                confidence_score=decision_data.get('confidence_score', 0.8)
            )

            # CTF Proactive: if surface score is low, do not skip core exploit agents
            if findings.attack_surface_score <= 1:
                for ea in ['xss', 'sqli', 'command_injection']:
                    if ea in self.AGENT_REGISTRY and self.AGENT_REGISTRY[ea]['available']:
                        if ea not in decision.priority_1 and ea not in decision.priority_2:
                            decision.priority_1.append(ea)
                            if ea in decision.skip:
                                decision.skip.remove(ea)
                            decision.reasoning[ea] = "CTF low attack surface: forced proactive probe"

            return decision"""

old_decision = old_decision.replace("\r\n", "\n")
if old_decision in text:
    text = text.replace(old_decision, new_decision)
    print("Patched CTF proactive agent decision")
else:
    print("old_decision not matched directly")

with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(text)
print("Saved intelligent_orchestrator.py")
