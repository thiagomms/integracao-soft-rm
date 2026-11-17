/* =====================================================================
   BAIXA DE LANÇAMENTO A PAGAR (FLAN) - consultas de apoio
   Rodar no banco de TESTE (BASE_TESTE). Somente SELECT.
   Comentários só com barra-asterisco: o RM quebra a sentença com dois hífens.
   ===================================================================== */

/* 1) ANTES da baixa: o lançamento existe, é A PAGAR e está EM ABERTO?
      Só chamar o wsProcess se STATUSLAN = 0. Se for 1 (baixado), NÃO reenviar
      (anti-duplicidade: a SoftExpert pode reenviar a mesma aprovação). */
SELECT  F.CODCOLIGADA, F.IDLAN, F.NUMERODOCUMENTO, F.PAGREC, F.STATUSLAN,
        F.CODCFO, F.DATAVENCIMENTO, F.VALORORIGINAL, F.VALORBAIXADO, F.IDMOV
FROM    FLAN F
WHERE   F.CODCOLIGADA = 1
  AND   F.IDLAN = 123456;   /* trocar pelo IDLAN */

/* 2) Achar o IDLAN a partir da nota (movimento) que a SoftExpert conhece. */
SELECT  T.IDMOV, T.NUMEROMOV, T.CODTMV, F.IDLAN, F.STATUSLAN, F.DATAVENCIMENTO, F.VALORORIGINAL
FROM    TMOV T
JOIN    FLAN F ON F.CODCOLIGADA = T.CODCOLIGADA AND F.IDMOV = T.IDMOV
WHERE   T.CODCOLIGADA = 1
  AND   T.IDMOV = 211266;   /* trocar pelo IDMOV */

/* 3) DEPOIS da baixa: conferir o registro gerado em FLANBAIXA. */
SELECT  B.IDLAN, B.IDBAIXA, B.DATABAIXA, B.CODCXA, B.IDFORMAPAGTO,
        B.VALORBAIXA, B.VALORJUROS, B.VALORDESCONTO, B.USUARIO, B.DATACANCELBAIXA
FROM    FLANBAIXA B
WHERE   B.CODCOLIGADA = 1
  AND   B.IDLAN = 123456;   /* trocar pelo IDLAN */

/* 4) Contas-caixa usadas nas baixas a pagar (para preencher {{codcxa}}). */
SELECT  B.CODCXA, X.DESCRICAO, COUNT(*) AS QTD
FROM    FLANBAIXA B
JOIN    FLAN F ON F.CODCOLIGADA = B.CODCOLIGADA AND F.IDLAN = B.IDLAN
JOIN    FCXA X ON X.CODCOLIGADA = B.CODCOLCXA AND X.CODCXA = B.CODCXA
WHERE   B.CODCOLIGADA = 1 AND F.PAGREC = 2
  AND   B.DATABAIXA >= DATEADD(month, -3, GETDATE())
  AND   B.DATACANCELBAIXA IS NULL
GROUP BY B.CODCXA, X.DESCRICAO
ORDER BY QTD DESC;
