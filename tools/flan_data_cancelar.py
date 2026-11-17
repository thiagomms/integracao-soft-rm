"""Teste da troca de previsao de baixa e do cancelamento de lancamento a pagar (FLAN) no RM.

Sem --enviar, so simula (le o lancamento e mostra o que seria enviado).

Uso:
  python flan_data_cancelar.py data      --idlan 413186 --nova-data 2026-12-21 [--enviar]
  python flan_data_cancelar.py cancelar  --idlan 413186 [--historico "..."] [--enviar]     (lancamento sem nota)
  python flan_data_cancelar.py cancelar-mov --idlan 409099 [--historico "..."] [--enviar]  (lancamento de nota: cancela o TMOV)
"""
import argparse
import os
import re
import sys
import time
from datetime import date
from html import escape, unescape
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rm_ws import _call  # noqa: E402  (carrega o .env)

PACOTE = Path(__file__).resolve().parent.parent / "Integracao SoftExpert x RM - pacote programador"
URL = os.environ["RM_URL"]
USER = os.environ["RM_USER"]
CTX = f"CODCOLIGADA=1;CODFILIAL=1;CODSISTEMA=F;CODUSUARIO={USER}"

ap = argparse.ArgumentParser()
ap.add_argument("acao", choices=["data", "cancelar", "cancelar-mov"])
ap.add_argument("--banco", default="BASE_PRODUCAO", help="banco do RM que o RM_URL atende (para 'cancelar-mov')")
ap.add_argument("--idlan", type=int, required=True)
ap.add_argument("--nova-data", help="AAAA-MM-DD (so para 'data')")
ap.add_argument("--historico", default=None)
ap.add_argument("--enviar", action="store_true")
a = ap.parse_args()


def tag(x, nome):
    m = re.search(rf"<{nome}>(.*?)</{nome}>", x, re.S)
    return m.group(1) if m else None


def ler():
    return _call(URL, "ReadRecord",
                 "<tot:ReadRecord><tot:DataServerName>FinLanDataBR</tot:DataServerName>"
                 f"<tot:PrimaryKey>1;{a.idlan}</tot:PrimaryKey><tot:Contexto>{CTX}</tot:Contexto></tot:ReadRecord>")


def resumo(x):
    return {k: tag(x, k) for k in ("IDLAN", "PAGREC", "STATUSLAN", "CODCFO", "VALORORIGINAL",
                                   "DATAVENCIMENTO", "DATAPREVBAIXA")}


print(f"Destino: {URL}")
lan = ler()
if not tag(lan, "IDLAN"):
    sys.exit(f"Lancamento {a.idlan} nao encontrado. Retorno: {lan[:500]}")
print("ANTES:", resumo(lan))
if tag(lan, "PAGREC") != "2":
    sys.exit("Nao e lancamento A PAGAR. Nada enviado.")
if tag(lan, "STATUSLAN") != "0":
    sys.exit(f"Lancamento nao esta em aberto (STATUSLAN={tag(lan, 'STATUSLAN')}). Nada enviado.")

if a.acao == "data":
    if not a.nova_data or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.nova_data):
        sys.exit("Informe --nova-data AAAA-MM-DD")
    novo = re.sub(r"<DATAPREVBAIXA>.*?</DATAPREVBAIXA>",
                  f"<DATAPREVBAIXA>{a.nova_data}T00:00:00</DATAPREVBAIXA>", lan, count=1)
    print(f"Troca: DATAPREVBAIXA {tag(lan, 'DATAPREVBAIXA')} -> {a.nova_data}T00:00:00 (resto do registro igual)")
    if not a.enviar:
        sys.exit("SIMULACAO: nada enviado. Use --enviar para gravar de verdade.")
    ret = _call(URL, "SaveRecord",
                "<tot:SaveRecord><tot:DataServerName>FinLanDataBR</tot:DataServerName>"
                f"<tot:XML><![CDATA[{novo}]]></tot:XML><tot:Contexto>{CTX}</tot:Contexto></tot:SaveRecord>")
    print("Retorno SaveRecord:", ret)
    depois = ler()
    print("DEPOIS:", resumo(depois))
    ok = ret.strip() == f"1;{a.idlan}" and tag(depois, "DATAPREVBAIXA", ).startswith(a.nova_data) \
        and tag(depois, "DATAVENCIMENTO") == tag(lan, "DATAVENCIMENTO")
    print("DATA ALTERADA" if ok else "FALHA: conferir retorno acima.")
    sys.exit(0 if ok else 1)

historico = a.historico or f"Cancelado via integracao SoftExpert - IDLAN {a.idlan}"
if a.acao == "cancelar-mov":
    import pyodbc
    cur = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        f"SERVER={os.environ['DB_SERVER']};DATABASE={a.banco};"
        f"UID={os.environ['DB_USERNAME']};PWD={os.environ['DB_PASSWORD']};"
        "TrustServerCertificate=yes;Encrypt=no;ApplicationIntent=ReadOnly", timeout=10).cursor()
    mov = cur.execute("SELECT T.IDMOV, T.NUMEROMOV, T.CODTMV, T.STATUS, T.VALORLIQUIDO FROM FLAN F JOIN TMOV T "
                      "ON T.CODCOLIGADA=F.CODCOLIGADA AND T.IDMOV=F.IDMOV WHERE F.CODCOLIGADA=1 AND F.IDLAN=?",
                      a.idlan).fetchone()
    if not mov:
        sys.exit("Este lancamento nao veio de movimento (sem IDMOV): use a acao 'cancelar'.")
    print("MOVIMENTO:", dict(zip(("IDMOV", "NUMEROMOV", "CODTMV", "STATUS", "VALORLIQUIDO"), mov)))
    if mov.STATUS == "C":
        sys.exit("Movimento ja cancelado. Nada enviado.")
    exp = cur.execute("SELECT STATUSEXPORTCONT, CODLOTE, DATACONTABILIZACAO FROM TMOV WHERE CODCOLIGADA=1 AND IDMOV=?",
                      mov.IDMOV).fetchone()
    if exp.STATUSEXPORTCONT == 1:
        sys.exit(f"Movimento ja foi exportado para a Contabilidade (lote {exp.CODLOTE}, {exp.DATACONTABILIZACAO:%d/%m/%Y}). "
                 "O RM recusa o cancelamento. A Contabilidade precisa desfazer a exportacao antes. Nada enviado.")
    rel = cur.execute("SELECT COUNT(*) FROM TMOVRELAC WHERE (CODCOLORIGEM=1 AND IDMOVORIGEM=?) "
                      "OR (CODCOLDESTINO=1 AND IDMOVDESTINO=?)", mov.IDMOV, mov.IDMOV).fetchone()[0]
    outros = cur.execute("SELECT COUNT(*) FROM FLAN WHERE CODCOLIGADA=1 AND IDMOV=? AND IDLAN<>?",
                         mov.IDMOV, a.idlan).fetchone()[0]
    if rel or outros:
        sys.exit(f"Movimento tem {rel} relacionamento(s) e {outros} outro(s) lancamento(s). "
                 "Cancelar pela tela do RM. Nada enviado.")
    modelo = (PACOTE / "45_ExecuteWithXmlParams_cancelar_TMOV.xml").read_text(encoding="utf-8")
    valores = {"rm_user": USER, "idmov": str(mov.IDMOV), "numeromov": mov.NUMEROMOV,
               "data_cancelamento": date.today().isoformat(), "motivo": escape(historico)}
else:
    modelo = (PACOTE / "43_ExecuteWithXmlParams_cancelar_FLAN.xml").read_text(encoding="utf-8")
    valores = {"rm_user": USER, "idlan": str(a.idlan), "data_cancelamento": date.today().isoformat(),
               "historico": escape(historico)}
envelope = re.sub(r"<!--.*?-->\s*", "", modelo, count=1, flags=re.S)
for k, v in valores.items():
    envelope = envelope.replace("{{" + k + "}}", v)
assert "{{" not in envelope, "marcador sem valor no envelope"
print("Cancelamento:", {k: v for k, v in valores.items() if k != "rm_user"})
if not a.enviar:
    sys.exit("SIMULACAO: nada enviado. Use --enviar para cancelar de verdade.")
resp = requests.post(f"{URL}/wsProcess/IwsProcess", data=envelope.encode("utf-8"),
                     headers={"Content-Type": "text/xml; charset=utf-8",
                              "SOAPAction": '"http://www.totvs.com/IwsProcess/ExecuteWithXmlParams"'},
                     auth=(USER, os.environ["RM_PASS"]), timeout=120)
m = re.search(r"<ExecuteWithXmlParamsResult>(.*)</ExecuteWithXmlParamsResult>", resp.text, re.S)
ret = unescape(m.group(1)) if m else unescape(resp.text)[:3000]
print("HTTP", resp.status_code, "| Retorno:", ret)
if resp.status_code != 200 or not m or "Exception" in ret:
    sys.exit("FALHA: o RM devolveu erro (HTTP 200 nao significa sucesso). Nada foi cancelado.")
for _ in range(12):
    depois = ler()
    if tag(depois, "STATUSLAN") != "0":
        break
    time.sleep(5)
print("DEPOIS:", resumo(depois))
if a.acao == "cancelar-mov":
    print("TMOV STATUS:", cur.execute("SELECT STATUS FROM TMOV WHERE CODCOLIGADA=1 AND IDMOV=?", mov.IDMOV).fetchone()[0])
print("CANCELADO" if tag(depois, "STATUSLAN") == "2" else "Ainda em aberto: conferir o Job Monitor do RM.")
