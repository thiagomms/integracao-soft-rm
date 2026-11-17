# Baixa de lançamento a pagar (FLAN): SoftExpert → RM

**Objetivo:** quando o pagamento for **aprovado na SoftExpert**, a SoftExpert chama o RM por SOAP e o RM **baixa** o lançamento a pagar (`FLAN`). A aprovação fica só na SoftExpert. Os campos de aprovação do RM (`LIBAUTORIZADA`, `STATUSAPROVACAO`) não são usados, porque nunca foram usados na base.

**Agora:** testar **somente na base de teste `BASE_TESTE`**. Baixa mexe em saldo bancário e contabilidade.

## Arquivos

| Arquivo | Para quê |
|---|---|
| `31_ExecuteWithXmlParams_baixa_FLAN.xml` | Envelope SOAP da baixa, com marcadores `{{...}}`. |
| `32_conferencia_baixa_FLAN.sql` | Conferir o lançamento antes da baixa (anti-duplicidade) e a baixa depois. |

## A chamada

```
POST {rm_url}/wsProcess/IwsProcess
Content-Type: text/xml; charset=utf-8
SOAPAction: "http://www.totvs.com/IwsProcess/ExecuteWithXmlParams"
Authorization: Basic base64(usuario:senha)

ProcessServerName = FinLanBaixaTBCData
strXmlParams      = <FinLanBaixaTBCParamsProc>...</FinLanBaixaTBCParamsProc>  (dentro de CDATA)
```

- **Classe de parâmetros:** o RM exige a `FinLanBaixaTBCParamsProc`. A `FinTBCBaixaParamsProc` foi recusada em 16/11/2026 com `SerializationException: Expecting element 'FinLanBaixaTBCParamsProc'`.
- **HTTP 200 não é sucesso:** o erro volta dentro do `ExecuteWithXmlParamsResult`. Sempre conferir a `FLAN` depois.
- O IDLAN vai em dois lugares: `PrimaryKeyList` e `Pagamentos/ListIdLan`. Conta-caixa, forma de pagamento e valor ficam em `Pagamentos/MeioPagamento`.
- Script de teste: `tools/baixar_flan.py` (sem `--enviar`, só simula).

- O serviço é o **`wsProcess`**, não o `wsDataServer` da OC. Os dois estão no mesmo RM.Host, com o mesmo usuário e senha.
- O XML de parâmetros foi **gerado a partir das classes do próprio RM** (`RM.Fin.Lan.Intf.dll`, classe `FinLanBaixaTBCParamsProc`). A ordem dos elementos importa: não reordene.
- **Decimal com ponto** (`1500.75`). É diferente do `SaveRecord` da OC, que segue o `WebServiceCulture` do Host.

## Fluxo na SoftExpert

1. Aprovação final do pagamento.
2. **Anti-duplicidade:** consultar a `FLAN` pelo `IDLAN` (consulta 1 do SQL). Só seguir se `STATUSLAN = 0` (em aberto). Se já estiver `1` (baixado), registrar como "já baixado" e não reenviar.
3. Chamar o `ExecuteWithXmlParams` com o XML preenchido.
4. Conferir a `FLANBAIXA` (consulta 3) e gravar o `IDBAIXA` no processo da SoftExpert.

## Campos

| Marcador | Origem | Observação |
|---|---|---|
| `{{idlan}}` | `FLAN.IDLAN` | Se a SoftExpert só conhece a nota, use a consulta 2 (`TMOV` → `FLAN`). |
| `{{data_baixa}}` | Data do pagamento | `AAAA-MM-DD` |
| `{{codcxa}}` | Conta-caixa de saída (`FCXA.CODCXA`) | Lista na consulta 4. |
| `{{valor}}` | Valor pago | Igual ao saldo em aberto para baixa total. |
| `{{historico}}` | Texto livre | Sugestão: `Baixa aprovada na SoftExpert - processo <id>`. |
| `{{evento}}` | Evento contábil da baixa (`FLANBAIXA.CODEVENTOBAIXA`) | **Obrigatório**: sem ele o RM recusa ("Favor informar o evento contábil"). Padrão `37`, usado em quase todas as baixas a pagar manuais; `43` e `45` aparecem em poucos casos. |
| Forma de pagamento | Fixo `11` | É a usada em todas as baixas a pagar da base. |
| Coligada da conta-caixa | Fixo `1` | |

## Validar no primeiro teste (base de TESTE)

1. **Porta do RM.Host de teste.** Confirme com a TI que o `RM_URL` do `.env` aponta para a base de **teste**, e não para a de produção.
2. **Processo × classe de parâmetros:** resolvido. `FinLanBaixaTBCData` exige `FinLanBaixaTBCParamsProc`.
3. **Retorno:** conferir se a execução é síncrona (retorno `1`/sucesso) ou se entra no Job Monitor. Se ficar assíncrona, avaliar `SyncExecution = true` nos parâmetros-base.
4. **Contabilização:** o bloco `Contabilizacao` usa o evento contábil padrão (`EventoContabil`). Confirmar com a contabilidade se a baixa gerada fica igual à manual.
5. **Desfazer:** cancelar a baixa de teste pela tela do RM (Fluxus → Lançamentos → Cancelar baixa), nunca por SQL.
