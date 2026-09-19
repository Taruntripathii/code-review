from backend.app.llm import build_default_llm, build_prompt, parse_llm_output

llm = build_default_llm()
prompt = build_prompt("app.py", [{"new_line": 12, "content": 'password = "admin123"'}])
raw = llm.analyze(prompt)
print("RAW:", raw)
print("PARSED:", parse_llm_output(raw, "app.py"))
