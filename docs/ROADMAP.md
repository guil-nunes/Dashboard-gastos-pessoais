# Roadmap de implementação — Dashboard de Gastos Pessoais (MVP)

Rota planejada para implementar a [spec do MVP](SPEC-MVP.md). Os identificadores `R#` e `Q#` referem-se aos requisitos e questões da spec.

**Princípios da rota**
- **Núcleo puro primeiro.** Domínio e pipeline de importação são testados só com fixtures, sem banco e sem HTTP (spec §7.2). A interface vem por cima.
- **Do formato mais simples ao mais difícil.** CSV/OFX do Nubank consolidam o pipeline antes dos parsers de PDF do Itaú.
- **Cada fase termina utilizável.** Ao fim da Fase 3 já é possível fazer o primeiro fechamento mensal real.
- **Testes como critério de pronto.** Nenhuma etapa fecha sem os testes listados nela.

## Visão geral

| Fase | Objetivo | Entrega utilizável | Requisitos |
|---|---|---|---|
| **0. Descoberta** ✅ | Formatos, regras e modelo definidos | Spec aprovada | — |
| **1. Importar** | Transações corretas no banco, sem duplicidade | Upload dos 4 formatos com resumo por arquivo | R1–R5 |
| **2. Categorizar e revisar** | Toda despesa com tipo e categoria revisáveis | Tela de revisão individual e em lote | R6 (estratégias 0–3), R7 |
| **3. Dashboard** | Fechar o mês | **Primeiro fechamento real** | R8 |
| **4. Recorrência e parcelas** | Ver compromissos futuros | Recorrentes, parcelas futuras, piso do mês | R9, R10, R12 |
| **5. Categorização avançada** | Menos revisão manual | Classificador local e Gemini opcional | R11 |

```
Fase 1 ──► Fase 2 ──► Fase 3 ──► Fase 4
                 └──────────────► Fase 5 (após ~100 transações revisadas)
```

---

## Fase 1 — Importar

Objetivo: importar os 4 formatos com competência, deduplicação e marcação estrutural corretas. A Fase 1 é dividida em etapas para validar o pipeline com os formatos simples antes dos PDFs.

### 1.1 Fundação do repositório
- [ ] Estrutura `backend/` conforme spec §7.3 (`api/`, `ingestion/`, `domain/`, `classification/`, `analytics/`, `repo/`)
- [ ] Gerenciamento de dependências e ambiente virtual; lint/format (ex.: ruff) e `pytest`
- [ ] Configuração por `.env` + `.env.example` (caminho do banco, nº de backups, parâmetros futuros)
- [ ] `frontend/` com React + Vite, proxy para o backend em dev (spec §7.5)
- [ ] README com como rodar backend, frontend e testes

**Pronto quando:** `pytest` e o frontend sobem do zero seguindo o README.

### 1.2 Domínio puro (`domain/`)
- [ ] Dinheiro em centavos: parsing de `"1.234,56"`, `"- 12,93"`, `-4350.29`, `TRNAMT` (R1)
- [ ] Datas: ISO, `DD/MM/AAAA`, OFX com fuso sem conversão para UTC, `DD/MM` com ano inferido pelo fechamento (R3)
- [ ] Normalizador versionado: `description_raw` → `merchant_key` com os casos reais da spec (R5)
- [ ] Extração de parcela `n/N` nos dois estilos: ` - Parcela 4/4` (Nubank) e `09/12` colado (Itaú)
- [ ] Competência: regra Nubank, regra Itaú e ajuste de antecipação (R3, Q14)
- [ ] `dedup_key`: `external_id` quando existe; hash + ordinal quando não (R2)
- [ ] `installment_group_key`: `description_root` + N + mês da parcela 1 (pela data da linha, antes do ajuste de antecipação) + ordinal (R10, Q11, Q14)

**Testes:** unitários para cada função, com os exemplos reais da spec (anonimizados).

### 1.3 Banco de dados (`repo/`)
- [ ] Modelos SQLAlchemy do §8: `account`, `import_batch`, `transactions`, `transaction_source`, `category`, `merchant_memory`, `keyword_rule`, `installment_group_override`, `llm_cache`, `recurrence_override`
- [ ] Alembic com a migração inicial e seed das 7 categorias
- [ ] `account.external_account_id NOT NULL DEFAULT ''` (sem duplicar contas no SQLite)
- [ ] Backup automático `VACUUM INTO backups/…` antes de cada importação, mantendo as 10 últimas

### 1.4 Pipeline de importação + adapters do Nubank
- [ ] Interface do adapter: `sniff(head: bytes) -> bool` e `parse(...) -> list[RawTransaction]`; registry que rejeita arquivos não reconhecidos
- [ ] Adapter **Nubank cartão CSV** (Anexo A.1)
- [ ] Adapter **OFX genérico** cobrindo a conta Nubank (Anexo A.2)
- [ ] (P1) Adapter **Nubank conta CSV** (Anexo A.3)
- [ ] Estágios `detect → parse → normalize → classify → keys → persist` (spec §7.2), com persistência em uma transação SQL por arquivo, gravando `transaction_source` também para as duplicatas
- [ ] Estratégia 0 (regras estruturais) já ligada ao estágio `classify`: crédito na conta, pagamento de fatura (R4, R6)
- [ ] Estorno como despesa negativa; IOF com o `merchant_key` da compra (Q9, Q10)

**Testes:**
- golden test por adapter, com fixtures anonimizadas em `backend/tests/fixtures/`;
- reimportar o mesmo arquivo não cria nada; duas corridas idênticas no mesmo dia são mantidas;
- **independência de ordem**: A→B, B→A e A∪B produzem o mesmo banco;
- sanidade do R4: o pagamento da fatura não conta como despesa.

### 1.5 Adapters do Itaú (PDF)
- [ ] Dependência de extração de PDF (ex.: `pdfplumber`)
- [ ] Adapter **Itaú conta PDF** (Anexo A.6.1): tabela de coluna única, data de lançamento, valor com sinal
- [ ] Adapter **Itaú cartão PDF** (Anexo A.6.2):
  - [ ] extração por coluna, sem intercalar as duas colunas da página
  - [ ] seções "compras e saques" e "produtos e serviços"; ignora "próximas faturas", resumo e simulações
  - [ ] ano inferido pela data de fechamento
  - [ ] `bank_category` preenchida a partir da linha de categoria
  - [ ] **conferência contra "Total dos lançamentos atuais"**; arquivo rejeitado se não bater
- [ ] Antecipação: parcelas do mesmo grupo no mesmo arquivo → competência da menor parcela (Q14)

**Testes:** golden tests com PDFs de fixture **gerados com dados inventados** (nunca os PDFs reais, que têm dados de terceiros); teste de rejeição por total divergente; teste de antecipação + estorno no mesmo mês.

### 1.6 API e tela de importação
- [ ] `POST /imports` (vários arquivos, resposta por arquivo), `GET /imports`, `DELETE /imports/{id}` (spec §7.4)
- [ ] Desfazer remove apenas transações sem outra origem em `transaction_source`
- [ ] Na primeira importação de uma conta, informar o titular (`account.holder`, Q15)
- [ ] Tela **Importar**: arrastar arquivos, ver o resumo (novas / duplicadas / erro / rejeitado) e desfazer
- [ ] Tipos TypeScript gerados do OpenAPI

**Testes:** desfazer com lotes sobrepostos (desfazer A ≡ importar só B).

**Pronto quando (Fase 1):** a carga histórica dos 4 formatos importa sem duplicidade, e a soma do cartão de cada mês confere com a fatura.

---

## Fase 2 — Categorizar e revisar

Objetivo: toda transação sai da importação com tipo e categoria sugeridos, e a revisão é rápida.

### 2.1 Pipeline de estratégias (`classification/`)
- [ ] Interface `Strategy` → `Classification(kind, ignore_reason, category, source, confidence, suggested_ignore_reason)` (R6)
- [ ] Estratégia 0: regras estruturais (já da Fase 1)
- [ ] Estratégia 1: memória por `merchant_key`, sem aplicar `investimento` automaticamente (Q15)
- [ ] Estratégia 2: regras de palavra-chave, com seed inicial (ex.: `Ifd*` → Alimentação, `Uber` → Transporte)
- [ ] Estratégia 3: categoria do banco, baixa confiança, com mapa editável (Q16)
- [ ] Sugestão de investimento para saídas ao mesmo titular e `APLICACAO COFRINHOS` (Q15)
- [ ] Correção manual atualiza a memória e recategoriza as não revisadas do mesmo estabelecimento; revisadas nunca são sobrescritas
- [ ] Comando `renormalize` para quando o normalizador mudar de versão (R5)

**Testes:** Pix recebido de alguém com memória de despesa continua `ignorar/receita`; revisadas não mudam ao reimportar; investimento nunca é aplicado sem confirmação.

### 2.2 API e tela de revisão
- [ ] `GET /transactions` com filtros; `PATCH /transactions/{id}` (corrigir ou confirmar)
- [ ] `GET /merchants?pending=true` e `POST /transactions/bulk-categorize` (R7)
- [ ] CRUD de `/categories` e `/rules`
- [ ] Tela **Revisar**: fila de pendentes e baixa confiança, agrupada por estabelecimento; aplicar ou confirmar em lote; confirmar sugestão de investimento em um clique

**Pronto quando:** a carga histórica inteira pode ser revisada em lote, e reimportar não desfaz nenhuma revisão.

---

## Fase 3 — Dashboard de fechamento

Objetivo: fechar o mês. **Ao fim desta fase, fazer o primeiro fechamento real e medir o tempo** (meta ≤ 15 min, spec §10).

- [ ] `GET /dashboard/summary?month=` e `GET /dashboard/history` (só `status = 'real'` e `kind = 'despesa'`)
- [ ] Tela **Dashboard** (R8):
  - [ ] seletor de mês de competência
  - [ ] total do mês e variação vs. mês anterior (R$ e %)
  - [ ] despesas por categoria (valor e %)
  - [ ] histórico mensal, total e por categoria
  - [ ] filtros por banco e por tipo (conta / cartão)
  - [ ] drill-down da categoria para as transações
  - [ ] estado vazio orientando a primeira importação
- [ ] FastAPI servindo o `frontend/dist`; um comando sobe tudo (spec §7.5)

**Pronto quando:** um mês fechado bate com a soma manual das faturas e extratos, descontando os itens ignorados.

---

## Fase 4 — Recorrência e parcelas

Objetivo: mostrar o que já está comprometido nos próximos meses.

### 4.1 Parcelas projetadas (R10)
- [ ] Reconstrução das projetadas ao fim de cada importação e de cada desfazer, na mesma transação SQL
- [ ] Categoria via `installment_group_override` ou última parcela real
- [ ] Sinalização de grupos com projetada vencida sem a parcela real (compra cancelada ou antecipada)
- [ ] `GET /installments/upcoming` e tela **Parcelas**
- [ ] Conferência opcional com "Próxima fatura" da fatura do Itaú

**Testes:** independência de ordem incluindo as projetadas; real substitui projetada; antecipação não gera grupo duplicado.

### 4.2 Recorrência (R9)
- [ ] Detector: ≥ 3 ocorrências, 25–35 dias, ±10% da mediana; parâmetros em configuração
- [ ] IOF somado à compra de origem; parcelas excluídas
- [ ] `GET /recurrences`, `PATCH /recurrences/{merchant_key}` e tela **Recorrentes**

### 4.3 Piso do próximo mês (R12)
- [ ] `GET /dashboard/floor?month=`: projetadas + último valor de cada recorrente, cartão e conta
- [ ] Card no dashboard com o detalhamento em parcelas e recorrentes

**Pronto quando:** o piso de um mês passado pode ser comparado com o gasto real daquele mês.

---

## Fase 5 — Categorização avançada

Pode começar em paralelo à Fase 4, depois de ~100 transações revisadas (Q6).

- [ ] Estratégia 4: classificador local (TF-IDF + Naive Bayes) treinado nas revisadas; ativado a partir de 100 revisadas
- [ ] Medição de acurácia em amostra separada antes de confiar no limite
- [ ] Estratégia 5: Gemini, desligado por padrão, enviando só a descrição normalizada, com cache por `merchant_key` e falha sem bloquear a importação
- [ ] Decidir como lidar com a latência do Gemini na carga inicial (limite por importação ou categorização posterior)

**Pronto quando:** a métrica "% categorizado automaticamente" (spec §10) é medida em um mês novo.

---

## Pendências que acompanham a rota

| Item | Quando resolver |
|---|---|
| **Q12** — estabilidade do ordinal quando a 1ª parcela traz o resto dos centavos | Ao aparecer o primeiro caso real; testar na Fase 4 |
| Apelidos de estabelecimento (`Nubank+` → `Nubank Croma`) | P2, após a Fase 4 |
| OFX do Itaú, se passar a existir | P2; substitui o adapter de PDF da conta |
