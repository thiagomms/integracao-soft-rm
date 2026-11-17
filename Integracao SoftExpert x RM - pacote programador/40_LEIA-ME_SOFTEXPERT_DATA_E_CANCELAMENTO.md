# SoftExpert → RM: previsão de baixa e cancelamento do lançamento a pagar

A SoftExpert faz duas operações no **lançamento a pagar** do RM (tabela `FLAN`), pelos web services SOAP do RM:

1. **Alterar a data de previsão de baixa** (`FLAN.DATAPREVBAIXA`). O vencimento não muda.
2. **Cancelar o lançamento.** Só o financeiro (`FLAN`); o movimento/nota (`TMOV`) continua existindo e pode ser relançado.

## Conexão

| Item | Valor |
|---|---|
| Endereço | `http://<HOST_RM>:<PORTA>`. A TI da a empresa informa o host e a porta (teste e produção). |
| Autenticação | HTTP Basic com usuário e senha do RM, também fornecidos pela TI. |
| Content-Type | `text/xml; charset=utf-8` |
| WSDL | Pasta `wsdl/`: `wsDataServer.wsdl` e `wsProcess.wsdl`. Também dá para baixar direto do RM em `/wsDataServer/MEX?singleWsdl` e `/wsProcess/MEX?singleWsdl`. |
| Coligada / filial | `1` / `1` |
| Sistema (Fluxus) | `F` |

Nos WSDLs, o endereço foi trocado por `SEU_RM_HOST:PORTA`. Ajuste para o host informado pela TI.

## 1. Alterar a previsão de baixa (`wsDataServer`)

| Passo | Operação | Arquivo |
|---|---|---|
| 1 | `ReadRecord` no DataServer `FinLanDataBR`, chave `1;<IDLAN>` | `41_ReadRecord_FinLanDataBR.xml` |
| 2 | Validar no retorno: `PAGREC = 2` e `STATUSLAN = 0` | |
| 3 | No XML lido, trocar **só** `<DATAPREVBAIXA>` | |
| 4 | `SaveRecord` no `FinLanDataBR` com o XML completo | `42_SaveRecord_FinLanDataBR_previsao_baixa.xml` |
| 5 | Sucesso = retorno `1;<IDLAN>`. Repetir o `ReadRecord` para conferir. | |

- Endpoint: `POST /wsDataServer/IwsDataServer`
- SOAPAction: `http://www.totvs.com/IwsDataServer/ReadRecord` e `.../SaveRecord`
- Contexto: `CODCOLIGADA=1;CODFILIAL=1;CODSISTEMA=F;CODUSUARIO=<usuario>`
- Data no formato `AAAA-MM-DDT00:00:00`, igual ao que o `ReadRecord` devolve.
- **Mande o registro inteiro** que veio do `ReadRecord`, com os blocos `FLAN`, `FLANCOMPL` e `FLANRATDEP`. Mandar só alguns campos pode zerar os demais ou mexer no rateio.

## 2. Cancelar o lançamento (`wsProcess`)

| Passo | Operação | Arquivo |
|---|---|---|
| 1 | Validar `PAGREC = 2` e `STATUSLAN = 0` (ReadRecord do passo anterior ou consulta 1 do SQL) | `44_conferencia_data_cancelamento.sql` |
| 2 | `ExecuteWithXmlParams`, processo `FinLanCancelamentoData` | `43_ExecuteWithXmlParams_cancelar_FLAN.xml` |
| 3 | Sucesso = retorno `1`. Conferir que `STATUSLAN` virou `2`. | |

- Endpoint: `POST /wsProcess/IwsProcess`
- SOAPAction: `http://www.totvs.com/IwsProcess/ExecuteWithXmlParams`
- O modelo de parâmetros (`FinLanCancelamentoParamsProc`) foi tirado do próprio RM com `GetSchema("FinLanCancelamentoData")`. **Não reordene os elementos.**
- O XML de parâmetros vai dentro de `<![CDATA[ ... ]]>`.

## Regras para os dois casos

- **HTTP 200 não quer dizer sucesso.** Quando o RM recusa, ele devolve o texto do erro (`System.Exception: ...`) dentro do resultado, com HTTP 200. Trate como sucesso só os retornos `1;<IDLAN>` (SaveRecord) e `1` (cancelamento).
- **Não reenviar** se o lançamento já estiver baixado (`STATUSLAN = 1`) ou cancelado (`STATUSLAN = 2`). Registre o caso na SoftExpert com uma mensagem clara.
- **Lançamento vindo de nota** (`IDMOV` preenchido): o cancelamento do `FLAN` é permitido no RM (há casos assim na base). Para relançar, lance o movimento de novo.
- **Testes:** primeiro na base de teste. Para desfazer um teste, use a tela do RM, nunca SQL.

## O que já foi validado (16/11/2026)

- WSDLs baixados do RM; as operações `ReadRecord`, `SaveRecord` e `ExecuteWithXmlParams` estão disponíveis.
- `ReadRecord` no `FinLanDataBR` funciona e devolve `DATAPREVBAIXA`. Teste só de leitura.
- O processo `FinLanCancelamentoData` existe no RM (`GetSchema`), e o XML do arquivo 43 é lido sem erro pelas classes do RM.
- **Ainda não executados:** o `SaveRecord` da data e o cancelamento. O primeiro teste de cada um deve ser na base de teste.
- O mesmo caminho (`wsProcess`) já baixou um lançamento real com sucesso, com o processo `FinLanBaixaTBCData` (arquivos 30 e 31).
