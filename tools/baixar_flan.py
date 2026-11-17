"""Baixa de um lancamento a pagar (FLAN) no RM via wsProcess (FinLanBaixaTBCData).

Sem --enviar, so mostra o que seria enviado (simulacao). Antes de enviar, confere no banco
se o lancamento esta EM ABERTO (anti-duplicidade) e, depois, le a FLANBAIXA gerada.

Uso:
  python baixar_flan.py --idlan 413058 --valor 4902.64 --data 2026-11-16 --codcxa 033-1 \
      --banco BASE_PRODUCAO [--historico "..."] [--enviar]
"""
import argparse
import os
import re
import sys
from html import escape, unescape
from pathlib import Path

import pyodbc
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
MODELO = Path(__file__).resolve().parent.parent / "Integracao SoftExpert x RM - pacote programador" / "31_ExecuteWithXmlParams_baixa_FLAN.xml"

ap = argparse.ArgumentParser()
ap.add_argument("--idlan", type=int, required=True)
ap.add_argument("--valor", required=True, help="ponto decimal, ex. 4902.64")
ap.add_argument("--data", required=True, help="AAAA-MM-DD (data do pagamento)")
ap.add_argument("--codcxa", required=True, help="conta-caixa, ex. 033-1")
ap.add_argument("--banco", default=os.environ.get("DB_DATABASE"), help="banco do RM que o RM_URL atende")
ap.add_argument("--historico", default=None)
ap.add_argument("--evento", type=int, default=37, help="evento contabil da baixa (CODEVENTOBAIXA); padrao 37")
ap.add_argument("--enviar", action="store_true", help="envia de verdade (sem isso, so simula)")
a = ap.parse_args()

if not re.fullmatch(r"\d+(\.\d{1,2})?", a.valor):
    sys.exit("Valor invalido: use ponto decimal, ex. 4902.64")
if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.data):
    sys.exit("Data invalida: use AAAA-MM-DD")

conn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.environ['DB_SERVER']};DATABASE={a.banco};"
    f"UID={os.environ['DB_USERNAME']};PWD={os.environ['DB_PASSWORD']};"
    "TrustServerCertificate=yes;Encrypt=no;ApplicationIntent=ReadOnly", timeout=10)
cur = conn.cursor()


def flan():
    return cur.execute(
        "SELECT IDLAN, PAGREC, STATUSLAN, CODCFO, VALORORIGINAL, VALORBAIXADO, DATAVENCIMENTO "
        "FROM FLAN WHERE CODCOLIGADA=1 AND IDLAN=?", a.idlan).fetchone()


def baixas():
    return cur.execute(
        "SELECT IDBAIXA, DATABAIXA, CODCXA, IDFORMAPAGTO, VALORBAIXA, USUARIO, DATACANCELBAIXA "
        "FROM FLANBAIXA WHERE CODCOLIGADA=1 AND IDLAN=?", a.idlan).fetchall()


lan = flan()
print(f"Banco {a.banco} | FLAN:", lan)
if not lan:
    sys.exit("Lancamento nao encontrado neste banco. Nada enviado.")
if lan.PAGREC != 2:
    sys.exit("Nao e lancamento A PAGAR (PAGREC<>2). Nada enviado.")
if lan.STATUSLAN != 0:
    sys.exit(f"Lancamento nao esta em aberto (STATUSLAN={lan.STATUSLAN}). Nada enviado.")
if (lan.VALORORIGINAL - lan.VALORBAIXADO) != __import__("decimal").Decimal(a.valor):
    print(f"ATENCAO: valor {a.valor} difere do saldo em aberto {lan.VALORORIGINAL - lan.VALORBAIXADO} (baixa parcial).")

historico = a.historico or f"Baixa via integracao SoftExpert - IDLAN {a.idlan}"
envelope = re.sub(r"<!--.*?-->\s*", "", MODELO.read_text(encoding="utf-8"), count=1, flags=re.S)
for k, v in {"rm_user": os.environ["RM_USER"], "data_baixa": a.data, "idlan": str(a.idlan),
             "codcxa": a.codcxa, "valor": a.valor, "historico": escape(historico),
             "evento": str(a.evento)}.items():
    envelope = envelope.replace("{{" + k + "}}", v)

url = os.environ["RM_URL"]
print(f"Destino: {url}/wsProcess/IwsProcess")
if not a.enviar:
    print(envelope.replace(os.environ["RM_USER"], "<RM_USER>"))
    sys.exit("\nSIMULACAO: nada enviado. Use --enviar para baixar de verdade.")

resp = requests.post(
    f"{url}/wsProcess/IwsProcess", data=envelope.encode("utf-8"),
    headers={"Content-Type": "text/xml; charset=utf-8",
             "SOAPAction": '"http://www.totvs.com/IwsProcess/ExecuteWithXmlParams"'},
    auth=(os.environ["RM_USER"], os.environ["RM_PASS"]), timeout=120)
print("HTTP", resp.status_code)
m = re.search(r"<ExecuteWithXmlParamsResult>(.*)</ExecuteWithXmlParamsResult>", resp.text, re.S)
retorno = unescape(m.group(1)) if m else unescape(resp.text)[:3000]
print("Retorno:", retorno)
if resp.status_code != 200 or not m or "Exception" in retorno or " at " in retorno:
    sys.exit("FALHA: o RM devolveu erro (HTTP 200 nao significa sucesso). Nada foi baixado.")

# O processo roda no Job Monitor do RM: aguarda a baixa aparecer.
import time
for _ in range(12):
    lan = flan()
    if lan.STATUSLAN != 0:
        break
    time.sleep(5)
print("FLAN depois:", lan)
for b in baixas():
    print("FLANBAIXA:", b)
print("BAIXADO" if lan.STATUSLAN == 1 else "Ainda em aberto: conferir o Job Monitor / log do processo no RM.")
