import os
TICKERS = ["RGTI","IONQ","QBTS","QUBT"]
COMPANIES = ["Rigetti","IonQ","D-Wave","Quantum Computing Inc","Quantinuum","PsiQuantum","Xanadu","Atom Computing","Pasqal","QuEra"]
ARXIV_QUERIES = ["quantum computing error correction","fault tolerant quantum","superconducting qubits","trapped ion quantum","neutral atom quantum","photonic quantum computing","Rigetti","IonQ","D-Wave"]
NEWS_KEYWORDS = ["Rigetti","IonQ","D-Wave","Quantum Computing Inc","quantum computing"]
PATENT_KEYWORDS = ["quantum computing","fault tolerant","superconducting","trapped ion"]
CIK = {"RGTI":"0001839550","IONQ":"0001824920","QBTS":"0001819913","QUBT":"0001526113"}
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK","")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT","email@example.com")
DATA_JSON = "docs/data.json"; SIGNALS_JSON="docs/signals.json"; STATE_JSON="data/state.json"
