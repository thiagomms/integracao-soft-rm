/* =====================================================================
   TROCA DA PREVISÃO DE BAIXA e CANCELAMENTO de lançamento a pagar (FLAN)
   Consultas de apoio. Somente SELECT.
   Comentários só com barra-asterisco: o RM quebra a sentença com dois hífens.
   STATUSLAN: 0 = em aberto, 1 = baixado, 2 = cancelado.
   ===================================================================== */

/* 1) ANTES: o lançamento é A PAGAR e está EM ABERTO?
      Só alterar a data ou cancelar se PAGREC = 2 e STATUSLAN = 0. */
SELECT  F.CODCOLIGADA, F.IDLAN, F.NUMERODOCUMENTO, F.PAGREC, F.STATUSLAN, F.CODCFO,
        F.DATAVENCIMENTO, F.DATAPREVBAIXA, F.VALORORIGINAL, F.IDMOV
FROM    FLAN F
WHERE   F.CODCOLIGADA = 1
  AND   F.IDLAN = 123456;   /* trocar pelo IDLAN */

/* 2) DEPOIS da troca de data: a previsão mudou e o vencimento ficou igual? */
SELECT  F.IDLAN, F.DATAVENCIMENTO, F.DATAPREVBAIXA, F.DATAALTERACAO
FROM    FLAN F
WHERE   F.CODCOLIGADA = 1
  AND   F.IDLAN = 123456;

/* 3) DEPOIS do cancelamento: STATUSLAN = 2 e data de cancelamento preenchida? */
SELECT  F.IDLAN, F.STATUSLAN, F.DATACANCELAMENTO, F.IDMOV
FROM    FLAN F
WHERE   F.CODCOLIGADA = 1
  AND   F.IDLAN = 123456;

/* 4) Achar o IDLAN a partir do movimento (nota) que a SoftExpert conhece. */
SELECT  T.IDMOV, T.NUMEROMOV, T.CODTMV, F.IDLAN, F.STATUSLAN, F.DATAVENCIMENTO, F.DATAPREVBAIXA
FROM    TMOV T
JOIN    FLAN F ON F.CODCOLIGADA = T.CODCOLIGADA AND F.IDMOV = T.IDMOV
WHERE   T.CODCOLIGADA = 1
  AND   T.IDMOV = 211266;   /* trocar pelo IDMOV */
