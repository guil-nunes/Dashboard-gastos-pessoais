# Spec — Dashboard de Gastos Pessoais (MVP)

| | |
|---|---|
| **Status geral** | Aprovado para implementação (Nubank). Pendentes: Itaú (Q1) e Q12 |
| **Autor** | guil-nunes |
| **Última atualização** | 2026-09-25 |
| **Stack** | FastAPI · SQLite · React (Vite) — execução 100% local |

**Legenda de status**
- ✅ **Aprovado** — decisão tomada, pode implementar.
- 🟡 **Não aprovado** — proposta; precisa de decisão antes de implementar (ver [Questões em aberto](#9-questões-em-aberto)).

---

## 1. Problema ✅

Ao fechar o mês, não tenho uma visão consolidada de quanto gastei e em quê. As despesas estão espalhadas entre **conta corrente e cartão de crédito**, em **dois bancos (Nubank e Itaú)**, e os extratos exportados vêm em formatos diferentes, com descrições pouco legíveis ("UBER *TRIP 8723") e sem categoria. Consolidar isso manualmente em planilha é trabalhoso, propenso a erro (ex.: contar a fatura do cartão duas vezes) e por isso acaba não sendo feito.

## 2. Objetivos ✅

1. **Fechar o mês em até 15 minutos**: da exportação dos arquivos no banco até o dashboard revisado.
2. **Categorização automática crescente**: após a revisão da carga histórica inicial, ≥ 80% das despesas de um mês novo recebem a categoria correta sem intervenção.
3. **Números confiáveis**: zero duplicidades e zero dupla contagem (pagamento de fatura / transferências entre contas não entram como despesa).
4. **Visibilidade de compromissos**: saber quais gastos são recorrentes e quanto já está comprometido em parcelas nos próximos meses.
5. **Aprendizado de arquitetura** (objetivo pessoal): backend em camadas com pontos de extensão claros (novo banco = novo adapter; nova forma de categorizar = nova estratégia).

## 3. Não-objetivos ✅

| Fora do escopo | Por quê |
|---|---|
| **Receitas, saldo e "quanto sobra para investir"** | Decisão do usuário; o projeto foca exclusivamente em despesas. |
| **Acompanhamento durante o mês / orçamento por categoria** | O uso é de fechamento mensal; acompanhamento é feito fora da ferramenta. |
| **Open Finance / integração automática com bancos** | Complexidade e dependência externa desproporcionais a um MVP local. Carga é por upload de arquivo. |
| **Multiusuário, autenticação, deploy em nuvem** | Uso pessoal e local. |
| **Bancos além de Nubank e Itaú** | Novos bancos entram depois, como novos adapters, conforme necessidade. |

## 4. Persona e fluxo principal ✅

**Persona única:** eu, usuário da ferramenta, que fecha o mês com os extratos de Nubank e Itaú (conta + cartão).

**Fluxo de uso**
1. **Carga inicial (uma vez):** faço upload de vários meses de histórico dos 4 tipos de arquivo e reviso as categorias em lote.
2. **Fechamento mensal (recorrente):** faço upload dos arquivos do mês → reviso apenas o que ficou sem categoria ou com baixa confiança → vejo o dashboard.

## 5. Histórias de usuário ✅

**Importação**
- Como usuário, quero **enviar o arquivo exportado pelo banco** (CSV/XLS) pela interface, para não precisar digitar despesas.
- Como usuário, quero **enviar vários arquivos de uma vez na carga inicial**, para montar meu histórico rapidamente.
- Como usuário, quero que **transações repetidas sejam ignoradas** se eu enviar um arquivo com período sobreposto, para que meu histórico não fique inflado.
- Como usuário, quero **ver um resumo após cada importação** (novas / duplicadas / com erro), para confiar no que foi carregado.
- Como usuário, quero **ser avisado quando um arquivo não for reconhecido**, em vez de ter dados importados errado silenciosamente.

**Classificação**
- Como usuário, quero que **pagamentos de fatura, transferências entre minhas contas e aportes sejam marcados como "ignorar"**, para que não contem como despesa.
- Como usuário, quero que **estornos abatam a despesa original**, para que uma compra cancelada não infle o mês.
- Como usuário, quero **receber uma sugestão de categoria** para cada despesa, para revisar em vez de classificar do zero.
- Como usuário, quero **corrigir uma categoria uma vez e que o sistema lembre** para aquele estabelecimento, para não repetir o trabalho no mês seguinte.
- Como usuário, quero **aplicar uma categoria a todas as transações do mesmo estabelecimento de uma vez**, para revisar a carga histórica rapidamente.
- Como usuário, quero **filtrar o que está sem categoria ou com baixa confiança**, para revisar só o necessário.

**Dashboard**
- Como usuário, quero **ver o total de despesas do mês por categoria**, para entender para onde foi o dinheiro.
- Como usuário, quero **comparar o mês com o anterior e com o histórico**, para identificar o que mudou.
- Como usuário, quero **filtrar por conta/cartão e por banco**, para analisar cada origem separadamente.
- Como usuário, quero **ver meus gastos recorrentes** (assinaturas, contas fixas), para identificar vazamentos.
- Como usuário, quero **ver as parcelas já comprometidas nos próximos meses**, para saber o que já está contratado.

## 6. Requisitos

### P0 — Obrigatórios

#### R1. Importação de arquivos ✅
Adapters para os 4 formatos: **Nubank conta**, **Nubank cartão**, **Itaú conta**, **Itaú cartão**.

- [ ] Upload de um ou mais arquivos via frontend (`.ofx`, `.csv`, `.xls`, `.xlsx`).
- [ ] O sistema detecta automaticamente banco e tipo (conta/cartão) pelo conteúdo do arquivo; se não reconhecer, rejeita o arquivo com mensagem clara e **nada é gravado**.
- [ ] Trata encoding (UTF-8 e Latin-1), separador `;`/`,`, datas `dd/mm/aaaa` e decimal com vírgula.
- [ ] Valores armazenados em **centavos (inteiro)** — nunca `float`.
- [ ] Cada importação gera um registro com: arquivo, conta, data, nº de linhas novas, duplicadas e com erro.
- [ ] Importação é **atômica por arquivo**: se falhar no meio, nada daquele arquivo é persistido.
- [ ] ✅ **Formatos suportados no MVP** (verificados em `samples/`, detalhes no [Anexo A](#anexo-a--formatos-de-arquivo-verificados)):
  - **Nubank cartão** → CSV (`date,title,amount`).
  - **Nubank conta** → **OFX** (preferencial). O CSV da conta traz os mesmos dados e o mesmo identificador; aceitá-lo é opcional (P1).
  - **PDF não é suportado** — o extrato em PDF da conta Nubank traz as mesmas transações do OFX/CSV, sem informação adicional.
- 🟡 **Itaú conta e Itaú cartão**: sem amostras ainda. Se o Itaú exportar OFX para a conta, o parser OFX genérico cobre os dois bancos. Ver Q1.

#### R2. Deduplicação ✅
- [ ] Enviar o mesmo arquivo duas vezes não cria nenhuma transação nova (curto-circuito por `file_sha256`, depois checagem por transação).
- [ ] Enviar arquivos com períodos sobrepostos cria apenas as transações que ainda não existem.
- [ ] Duas compras legítimas idênticas no mesmo dia **não** são descartadas como duplicata. Caso real observado na fatura Nubank: `2026-08-24, Uber - NuPay, 4,74` aparece duas vezes.
- [ ] ✅ **Chave de deduplicação** (`dedup_key`, única no banco):
  - **Arquivos com identificador nativo** (OFX `FITID`, coluna `Identificador` do CSV da conta Nubank): `conta + external_id`.
  - **Arquivos sem identificador** (CSV do cartão Nubank): `hash(conta + data + valor_centavos + description_raw + ordinal)`, onde `ordinal` é a posição (1, 2, 3…) da linha entre as linhas **idênticas** (mesma data, valor e descrição) **dentro do mesmo arquivo**. O ordinal não depende da ordem das linhas no arquivo.
- [ ] **Independência de ordem:** importar A e depois B, B e depois A, ou A ∪ B de uma vez produz exatamente o mesmo banco (transações reais e projetadas). Coberto por teste de propriedade.
- Risco aceito: se o banco alterar o texto da descrição de uma transação entre duas exportações, ela seria importada duas vezes. Mitigação: o resumo de importação destaca possíveis duplicatas (mesma conta, data e valor) para revisão.

#### R3. Competência ✅
- [ ] ✅ Compras à vista no cartão: competência = **mês da data da compra**.
- [ ] ✅ Transações de conta corrente: competência = mês da data da transação.
- [ ] ✅ Compras parceladas: a **1ª parcela** tem competência no mês da data da compra; cada parcela seguinte entra **mês a mês** — parcela `n/N` tem competência = mês da compra + (n−1) meses. O valor de cada mês é o valor da parcela, não o total da compra.
- [ ] ✅ **Verificado no CSV do cartão Nubank:** as parcelas `n ≥ 2` vêm com a **data de abertura do ciclo da fatura** (todas em `2026-08-01` na amostra), e não com a data da compra original. Portanto, para o Nubank, competência da parcela = mês da data da linha — o que já produz o "mês a mês" sem cálculo adicional.
- [ ] ✅ **Verificado:** a parcela `1/N` vem com a **data real da compra** (ex.: `2026-07-02, Pag*Steam - Parcela 1/3` na fatura de ago/2026, fora do dia 01 do ciclo). A parcela `2/3` aparece na fatura seguinte datada em `2026-08-01`. Regra única para o Nubank: **competência = mês da data da linha**, para compras à vista e para qualquer parcela.
- [ ] Datas com fuso (ex.: OFX `DTPOSTED …[-3:BRT]`) usam a **data local como veio no arquivo** — nunca convertidas para UTC, para uma compra às 22h do dia 31 não mudar de mês.
- Premissa: nas duas faturas analisadas o ciclo vai do dia 01 ao fim do mês. Se o dia de fechamento do cartão mudar, rever a regra das parcelas `n ≥ 2`.

#### R4. Marcação despesa × ignorar ✅
- [ ] Toda transação tem um tipo: `despesa` ou `ignorar` (com motivo: `pagamento_fatura`, `transferencia_interna`, `investimento`, `receita`, `outro`).
- [ ] Regras padrão, derivadas das amostras (as **estruturais**, baseadas em sinal/tipo de conta, rodam como estratégia 0 do R6, antes da memória):
  - Conta: **todo crédito** (valor de entrada) → `ignorar/receita` (inclui "Transferência recebida", "Crédito em conta").
  - Conta: `Pagamento de fatura` → `ignorar/pagamento_fatura`.
  - Cartão: `Pagamento recebido` (valor negativo) → `ignorar/pagamento_fatura`.
  - Conta: transferência enviada para contas do próprio titular (nome do titular configurável em `.env`) → `ignorar/transferencia_interna`.
- [ ] **Pix enviado para terceiros** entra como `despesa` **sem categoria**, para revisão manual; o `merchant_key` é o nome do destinatário, então a memória (R6) aprende por pessoa.
- [ ] ✅ **Estornos** (valor negativo no cartão que não é pagamento; ex.: `Uber - NuPay, - 12,93` que anula uma compra de `12,93` no mesmo dia) entram como **`despesa` com valor negativo** na categoria do estabelecimento, abatendo o total.
- [ ] ✅ **Impostos agregados** (ex.: `IOF de "Anthropic* Claude Sub"`) entram como `despesa` e **herdam a categoria da compra original**: o `merchant_key` é o do estabelecimento citado, então seguem a mesma memória/regra e acompanham correções feitas nele.
- [ ] As regras de tipo são executadas pelo **mesmo pipeline de estratégias do R6**: cada estratégia devolve tipo (`despesa`/`ignorar` + motivo) e categoria juntos.
- [ ] Usuário pode alterar o tipo manualmente; a alteração é lembrada para o mesmo estabelecimento (via R6).
- Risco aceito: um estorno de compra no débito chega na conta como crédito e é marcado `ignorar/receita` pela regra "todo crédito" — não abate a categoria, ao contrário do estorno no cartão. O usuário pode corrigir manualmente.
- [ ] Apenas `despesa` entra em qualquer total do dashboard.
- [ ] **Teste de sanidade:** a soma das despesas de cartão com competência no mês não inclui o pagamento da fatura lançado na conta.

#### R5. Normalização de descrição ✅
- [ ] Cada transação guarda a descrição original (`description_raw`) e uma chave normalizada do estabelecimento (`merchant_key`).
- [ ] A normalização remove ruído: códigos, números de transação, asteriscos, cidade/UF, sufixos de parcela. Casos reais das amostras:
  - `Ifd*Sushi Mais Japones` → `SUSHI MAIS JAPONES` (prefixo `Ifd*` = iFood; é um bom sinal para regra de Alimentação)
  - `Latam Air*0000 - Parcela 4/4` → `LATAM AIR` (+ parcela 4 de 4 extraída para os campos de parcela)
  - `Dm*Helphbomaxcom`, `Mp *Espain`, `Pag*Steam`, `App *Piuka` → remover prefixos de adquirente/gateway (`Dm*`, `Mp *`, `Pag*`, `App *`)
  - `IOF de "Anthropic* Claude Sub"` → `ANTHROPIC CLAUDE SUB` (mesmo `merchant_key` da compra, para herdar a categoria — Q10)
  - `Compra no débito - POSTO RUI BARBOSA` (conta) → `POSTO RUI BARBOSA`
  - `Transferência enviada pelo Pix - NOME - CPF mascarado - BANCO ...` → `PIX NOME`
- [ ] A normalização é determinística e coberta por testes com exemplos reais anonimizados.
- [ ] O normalizador tem uma **versão** (`normalizer_version`, gravada em cada transação). Ao mudar as regras, um comando `renormalize` recalcula os `merchant_key` e migra as chaves de `merchant_memory`, `llm_cache` e `recurrence_override`; quando duas chaves antigas colapsam na mesma, prevalece a memória atualizada mais recentemente.
- [ ] `merchant_key` **não** é usado em chaves de identidade (dedup, grupo de parcelas) — só em categorização e agrupamento, pois muda quando a normalização evolui.

#### R6. Categorização por pipeline de estratégias ✅
Ordem de execução — para na primeira estratégia que responder com confiança suficiente:

| # | Estratégia | Fase |
|---|---|---|
| 0 | **Regras estruturais** — crédito na conta → `ignorar/receita`; `Pagamento de fatura` / `Pagamento recebido` → `ignorar/pagamento_fatura`; transferência para o titular → `ignorar/transferencia_interna`. Rodam antes da memória e só são sobrepostas por correção manual **na própria transação** (nunca pela memória do estabelecimento) | P0 |
| 1 | **Memória do usuário** — correções anteriores por `merchant_key` (confiança 1.0) | P0 |
| 2 | **Regras de palavra-chave** — ex.: contém `IFOOD` → Alimentação | P0 |
| 3 | **Classificador local** (TF-IDF + Naive Bayes, treinado no histórico já revisado) | P1 |
| 4 | **Gemini API** (fallback opcional para o que sobrar) | P1 |

- [ ] Cada estratégia implementa a mesma interface e devolve um único resultado `Classification(kind, ignore_reason, category, source, confidence)` — tipo (R4) e categoria vêm juntos; adicionar/remover estratégia não altera as demais.
- [ ] Cada transação registra **origem** da categoria (`memoria`, `regra`, `classificador`, `gemini`, `manual`, `nenhuma`) e **confiança**.
- [ ] Cada transação registra se foi **revisada** (`reviewed_at`): preenchido quando o usuário corrige **ou confirma** a sugestão sem alterar.
- [ ] Correção manual atualiza a memória do usuário e **recategoriza as transações ainda não revisadas** (`reviewed_at IS NULL`) do mesmo estabelecimento.
- [ ] Transações revisadas **nunca** são sobrescritas por estratégias automáticas.
- Motivo da estratégia 0: `Transferência enviada pelo Pix - FULANO` e `Transferência recebida pelo Pix - FULANO` podem gerar o mesmo `merchant_key`. Sem ela, a memória "despesa/Alimentação" aprendida no Pix enviado seria aplicada ao Pix recebido, que entraria como despesa negativa e reduziria o total do mês silenciosamente.

#### R7. Revisão de categorias ✅
- [ ] Lista de transações filtrável por mês, conta, categoria, origem e "sem categoria / baixa confiança".
- [ ] Edição individual de categoria e de tipo (despesa/ignorar).
- [ ] **Confirmar sugestão** (individual ou em lote) marca como revisada sem alterar a categoria, tirando o item da fila de pendentes.
- [ ] **Revisão em lote agrupada por estabelecimento**: "aplicar categoria X às N transações de `IFOOD`".

#### R8. Dashboard de fechamento ✅
- [ ] Seletor de mês de competência.
- [ ] Total de despesas do mês e variação vs. mês anterior (R$ e %).
- [ ] Despesas por categoria no mês (valor e % do total).
- [ ] Histórico mensal de despesas (total e por categoria) para todo o período carregado.
- [ ] Filtro por banco e por tipo de conta (conta / cartão).
- [ ] Drill-down: clicar em uma categoria lista as transações que a compõem.
- [ ] Estado vazio: sem dados, o dashboard orienta a fazer a primeira importação.

### P1 — Desejáveis

#### R9. Detector de recorrência ✅
- [ ] ✅ Uma série é recorrente quando o mesmo `merchant_key` tem **no mínimo 3 ocorrências** em que:
  - o intervalo entre ocorrências consecutivas fica **entre 25 e 35 dias**; e
  - o valor de cada ocorrência fica a **±10% da mediana** da série.
- [ ] Impostos agregados (Q10) são somados à compra de origem antes da análise, para não distorcer o valor da série.
- [ ] Parcelas (`n/N`) **não** entram na detecção de recorrência — já são tratadas em R10.
- [ ] Parâmetros ficam em configuração (não fixos no código), para ajuste após uso real.
- Limitação conhecida: se o banco renomear o estabelecimento, a série se quebra (ex.: `Nubank+` em jul/2026 virou `Nubank Croma` em ago/2026, mesmo valor de R$ 29,00). Mitigação futura (P2): permitir unir dois `merchant_key` como apelidos do mesmo estabelecimento.
- [ ] Lista de recorrentes com: estabelecimento, valor médio, último lançamento, nº de meses.
- [ ] Usuário pode marcar um item detectado como "não é recorrente".

#### R10. Parcelas futuras ✅
- [ ] Identifica parcelas pelo padrão `n/N` na descrição.
- [ ] Mostra, por mês futuro, o total já comprometido e a lista de compras parceladas que o compõem.
- [ ] ✅ **Identidade da compra parcelada** (`installment_group_key`, Q11/Q12):
  `hash(conta + description_root + N + mês da parcela 1 + ordinal)`, onde:
  - `description_root` = `description_raw` sem o sufixo ` - Parcela n/N` (estável; **não** usa `merchant_key`, que muda com o normalizador — R5);
  - mês da parcela 1 = competência − (n−1) meses;
  - `ordinal` = posição da linha entre as linhas do **mesmo arquivo** com mesmos `description_root`, N e n, ordenadas por valor. Distingue compras parceladas idênticas no mesmo mês (sem ele, a segunda violaria a unicidade e derrubaria o arquivo inteiro).
  - O **valor da parcela não entra na chave**: parcelas com diferença de centavos (resto do arredondamento na 1ª) continuam no mesmo grupo.
- [ ] ✅ **Parcelas futuras são gravadas como transações com `status = 'projetada'`** (Q4), tratadas como **dado derivado e reconstruído**:
  - Ao fim de cada importação (na mesma transação SQL), as projetadas das contas afetadas são apagadas e regeneradas: para cada grupo, a partir da maior parcela real `n`, criam-se `n+1 … N` com competência nos meses seguintes e o valor da última real.
  - Nunca coexistem real e projetada para o mesmo número (`UNIQUE(installment_group_key, installment_number)`); a real sempre prevalece e vale o valor real.
  - Por ser reconstrução completa, o resultado independe da ordem de importação (R2); desfazer uma importação remove o lote, apaga só as transações que ficaram sem nenhuma origem (`transaction_source`) e reconstrói as projetadas.
  - Categoria das projetadas: a do override do grupo (`installment_group_override`), se houver; senão, a da última parcela real. Corrigir a categoria de qualquer parcela do grupo grava o override.
- [ ] Transações projetadas **não entram** nos totais do dashboard de fechamento (R8), no detector de recorrência (R9) nem no treino do classificador (R11). Aparecem apenas na visão de parcelas futuras (e no card de piso, R12).
- [ ] Grupos cuja próxima parcela projetada tem competência em um mês **já coberto por importação** daquela conta, sem a real correspondente, são sinalizados para revisão (ex.: compra cancelada ou antecipada).

#### R11. Classificador local e Gemini ✅
- [ ] Classificador local só é ativado a partir de **100 transações revisadas** (`reviewed_at IS NOT NULL`, corrigidas ou confirmadas). Limite configurável (Q6).
- [ ] Antes de confiar no limite, medir a acurácia do classificador em uma amostra separada das revisadas.
- [ ] Gemini é **desligado por padrão**; ligado por variável de ambiente com chave própria.
- [ ] Ao usar Gemini, envia **apenas a descrição normalizada** — nunca valores, datas ou dados da conta.
- [ ] Respostas do Gemini são cacheadas por `merchant_key` (não consultar o mesmo estabelecimento duas vezes).
- [ ] Falha/timeout da API não bloqueia a importação: a transação fica "sem categoria".

#### R12. Card "piso do próximo mês" ✅
Valor mínimo de despesas já comprometido no mês seguinte: **parcelas projetadas + gastos recorrentes**. É um piso, não uma previsão — não estima gastos variáveis.

- [ ] O piso é do **mês seguinte ao mês selecionado** no dashboard (fechando set/2026, mostra out/2026). Funciona também para meses passados, permitindo comparar piso × gasto real.
- [ ] Parcelas: soma das transações `projetada` com competência no mês-alvo (R10).
- [ ] Recorrentes: para cada série detectada (R9) e não marcada como "não é recorrente", usa o valor do **último lançamento** (inclui imposto agregado, ex.: IOF).
- [ ] Inclui recorrências de **cartão e conta**, desde que as transações sejam `despesa` (Pix recorrente marcado como `ignorar` fica fora).
- [ ] O card mostra o total e o detalhamento em dois grupos (parcelas / recorrentes), com cada item e valor.
- [ ] Sem parcelas nem recorrentes para o mês-alvo, o card mostra R$ 0,00 com a explicação.

### P2 — Considerações futuras (não construir, mas não impedir)
- **Novos bancos**: adicionar um banco deve exigir apenas um novo adapter + testes com arquivo exemplo.
- **OFX como caminho padrão**: o parser OFX genérico já é P0 (conta Nubank); com mais bancos, pode substituir adapters específicos.
- **Apelidos de estabelecimento**: unir dois `merchant_key` como o mesmo estabelecimento (R9).
- **Importação de PDF de fatura**, caso algum banco só ofereça esse formato.
- **Subcategorias** (ex.: Alimentação → Delivery / Restaurante).
- **Exportação** dos dados consolidados (CSV).

## 7. Arquitetura ✅

> Aprovada em 2026-09-25, com ressalva: adapters do Itaú pendentes de amostras (Q1).

> Revisada em 2026-09-25 após avaliação de arquitetura: pipeline de importação explícito com núcleo puro, `services/` desmembrado, R4 dentro do pipeline de estratégias, projeções reconstruídas, endpoints complementares.

### 7.1 Premissas de escala
- ~150–300 transações/mês, 4 contas (~3–4 mil/ano); um usuário, local, sem concorrência.
- Consequência: **sem fila, cache ou workers**. Endpoints síncronos (`def`) com SQLAlchemy síncrono; recorrências, agregações e piso calculados sob demanda.

### 7.2 Pipeline de importação

A importação é uma sequência de estágios. Tudo antes da persistência é **puro** (sem banco), testável só com fixtures; o acesso ao banco fica na borda.

```
upload ─► detect ─► parse ─► normalize ─► classify ─► keys ─► persist
          (registry  (adapter  (R5)        tipo (R4)    dedup   1 transação SQL por arquivo:
           sniff())   → Raw-                + categoria  (R2) +  grava lote, transações novas e
                                                                  origens (transaction_source) de
                                                                  todas as linhas, inclusive duplicatas;
                      Transaction)          (R6)         grupo   reconstrói projetadas (R10)
                                                         parcela
          └──────────────── núcleo puro, sem DB ────────────────┘ └──────── borda ────────┘
```

### 7.3 Estrutura do repositório

```
frontend/  (React + Vite)
  pages: Importar · Revisar · Dashboard · Recorrentes · Parcelas
  api/            # tipos TS gerados do OpenAPI do backend (openapi-typescript)

backend/   (FastAPI)
  app/
    api/            # rotas finas; DTOs Pydantic
    ingestion/
      adapters/     # NubankCardCsv, OfxAdapter, ... → list[RawTransaction]
      registry.py   # cada adapter expõe sniff(head: bytes) -> bool; nenhum casou → rejeita
      pipeline.py   # orquestra os estágios do 7.2
    domain/         # puro: dinheiro, competência, dedup_key, parcelas, normalizador
    classification/ # interface Strategy + pipeline: memória, regras, classificador, Gemini
                    #   saída única: Classification(kind, ignore_reason, category, source, confidence)
    analytics/      # só leitura: agregações do dashboard, recorrência (R9), piso (R12)
    repo/           # modelos SQLAlchemy, sessão, consultas
  migrations/       # Alembic desde o primeiro dia (o modelo vai mudar com o Itaú)
  tests/
    fixtures/       # arquivos de exemplo anonimizados por banco (versionados)

samples/           # arquivos reais, NÃO versionados (.gitignore); só para desenvolver os adapters
backups/           # cópias automáticas do banco (não versionadas)
```

### 7.4 Endpoints

| Método | Rota | Uso |
|---|---|---|
| `POST` | `/imports` | Upload de um ou mais arquivos. Responde **por arquivo** (novas / duplicadas / erro / rejeitado) com 200, mesmo que algum arquivo seja rejeitado |
| `GET` | `/imports` | Histórico de importações |
| `DELETE` | `/imports/{id}` | Desfaz uma importação: remove o lote, apaga as transações que não têm outra origem (`transaction_source`) e reconstrói as projetadas |
| `GET` | `/transactions` | Lista filtrável (mês, conta, categoria, origem, pendentes) |
| `PATCH` | `/transactions/{id}` | Alterar categoria / tipo, ou confirmar sugestão |
| `GET` | `/merchants?pending=true` | Pendentes agrupados por `merchant_key`, com contagem e sugestão (revisão em lote, R7) |
| `POST` | `/transactions/bulk-categorize` | Aplicar categoria/tipo, ou confirmar, por `merchant_key` |
| `GET` · `POST` · `PATCH` | `/categories` | Listar / criar / editar categorias |
| `GET` · `POST` · `PATCH` · `DELETE` | `/rules` | Manter as regras de palavra-chave |
| `GET` | `/dashboard/summary?month=` | Totais e por categoria do mês |
| `GET` | `/dashboard/history` | Série mensal |
| `GET` | `/dashboard/floor?month=` | Piso do mês seguinte (R12) |
| `GET` | `/recurrences` | Recorrentes detectados |
| `PATCH` | `/recurrences/{merchant_key}` | Marcar "não é recorrente" (R9) |
| `GET` | `/installments/upcoming` | Parcelas futuras por mês e grupos sinalizados (R10) |

### 7.5 Execução e confiabilidade
- **Dev:** Vite com proxy para o backend (sem CORS). **Uso real:** FastAPI serve o `frontend/dist`, e tudo sobe com um comando.
- **Backup:** antes de cada importação, `VACUUM INTO backups/AAAA-MM-DD_HHMMSS.db`, mantendo as **10** últimas cópias (configurável).
- **Testes:**
  - golden test por adapter, com fixtures;
  - testes do normalizador com casos reais;
  - teste de propriedade de **independência de ordem** da importação (R2), incluindo as projetadas;
  - teste de sanidade do R4 (a fatura não conta duas vezes);
  - teste de desfazer com lotes sobrepostos: importar A e B com períodos sobrepostos, desfazer A → o banco fica igual a importar só B;
  - teste da estratégia 0: Pix recebido de alguém com memória de despesa continua `ignorar/receita`.

## 8. Modelo de dados ✅

> Aprovado em 2026-09-25, com ressalvas: (1) os formatos do Itaú (Q1) podem exigir campos adicionais, que entram por migração Alembic; (2) a composição do `installment_group_key` segue válida, mas a estabilidade do ordinal com amostras do Itaú fica para verificação posterior (Q12).

```
account
  id                   PK
  bank                 TEXT   -- 'nubank' | 'itau'
  kind                 TEXT   -- 'conta' | 'cartao'
  external_account_id  TEXT NOT NULL DEFAULT ''  -- ex.: <ACCTID> do OFX; '' quando o arquivo não identifica (CSV do cartão Nubank)
  name                 TEXT   -- rótulo exibido
  UNIQUE(bank, kind, external_account_id)  -- '' em vez de NULL: no SQLite, NULLs são distintos em UNIQUE e permitiriam contas duplicadas

import_batch                     -- só importações bem-sucedidas são gravadas
  id              PK
  account_id      FK → account
  filename        TEXT
  file_sha256     TEXT UNIQUE    -- curto-circuito de arquivo repetido (R2)
  imported_at     DATETIME
  rows_total      INT
  rows_new        INT
  rows_duplicate  INT
  rows_error      INT

category
  id              PK
  name            TEXT UNIQUE
  color           TEXT
  is_active       BOOL

transactions                     -- plural: TRANSACTION é palavra-chave do SQL
  id                   PK
  account_id           FK → account
  import_batch_id      FK → import_batch NULL  -- lote que CRIOU a transação (informativo); NULL nas projetadas. Origens completas em transaction_source
  occurred_on          DATE      -- data local como veio no arquivo (sem conversão de fuso, R3)
  competence_month     TEXT      -- 'YYYY-MM' (ver R3 / Q2)
  amount_cents         INT       -- positivo = saída de dinheiro (o CSV do cartão Nubank já usa essa convenção; OFX/CSV da conta usam a inversa → inverter o sinal)
  description_raw      TEXT
  external_id          TEXT NULL -- FITID do OFX / Identificador do CSV da conta; NULL no cartão Nubank
  merchant_key         TEXT      -- descrição normalizada (R5); NÃO usado em chaves de identidade
  normalizer_version   INT       -- versão do normalizador que gerou o merchant_key (R5)
  kind                 TEXT      -- 'despesa' | 'ignorar'  (estorno = despesa com amount negativo)
  ignore_reason        TEXT NULL -- 'pagamento_fatura' | 'transferencia_interna' | 'investimento' | 'receita' | 'outro'
  category_id          FK → category NULL
  category_source      TEXT      -- 'memoria' | 'regra' | 'classificador' | 'gemini' | 'manual' | 'nenhuma'
  category_confidence  REAL NULL
  reviewed_at          DATETIME NULL -- usuário corrigiu ou confirmou (R6/R7); revisadas nunca são sobrescritas
  installment_number   INT NULL  -- n de n/N
  installment_total    INT NULL  -- N de n/N
  installment_group_key TEXT NULL -- hash(conta + description_root + N + mês da parcela 1 + ordinal); sem valor e sem merchant_key (R10, Q11/Q12)
  status               TEXT      -- 'real' | 'projetada'  (Q4)
  dedup_key            TEXT UNIQUE  -- projetadas usam 'proj:' + installment_group_key + ':' + n
  UNIQUE(installment_group_key, installment_number)  -- garante uma única parcela (real ou projetada) por número
  created_at           DATETIME
  INDEX(competence_month, status, kind)
  INDEX(merchant_key)

transaction_source               -- todos os lotes que contêm a transação (inclusive os que a viram como duplicata)
  transaction_id   FK → transactions ON DELETE CASCADE
  import_batch_id  FK → import_batch ON DELETE CASCADE
  PK(transaction_id, import_batch_id)
  -- desfazer um lote apaga as transações reais que ficam sem nenhuma linha aqui (R10, endpoint DELETE /imports/{id})

installment_group_override       -- R10: categoria definida pelo usuário para o grupo; sobrevive à reconstrução das projetadas
  installment_group_key  PK
  category_id            FK → category NULL
  updated_at             DATETIME

merchant_memory                  -- estratégia 1 (R6)
  merchant_key    PK
  category_id     FK → category NULL
  kind            TEXT NULL      -- permite lembrar 'ignorar'
  updated_at      DATETIME

keyword_rule                     -- estratégia 2 (R6)
  id              PK
  pattern         TEXT
  match_type      TEXT           -- 'contains' | 'regex'
  category_id     FK → category NULL
  kind            TEXT NULL
  priority        INT

llm_cache                        -- R11 (Gemini)
  merchant_key    PK
  category_id     FK → category NULL
  raw_response    TEXT
  created_at      DATETIME

recurrence_override              -- R9: "não é recorrente"
  merchant_key    PK
  is_recurring    BOOL
```

**Decisões embutidas no modelo**
- Valores em centavos inteiros; sinal normalizado para "positivo = saída", independente da convenção de cada banco.
- `competence_month` materializado como coluna (facilita agregações) em vez de calculado na consulta.
- Recorrências **calculadas sob demanda** (sem tabela de séries), apenas com tabela de override.
- Projetadas **gravadas** (Q4), mas tratadas como dado derivado: reconstruídas a cada importação ou desfazer (R10).
- Chaves de identidade (`dedup_key`, `installment_group_key`) dependem só de dados brutos do arquivo, nunca do normalizador.
- Categorias em lista plana (sem hierarquia) no MVP.

**Categorias iniciais** ✅ (seed da tabela `category`; lista plana, editável pelo usuário):
Moradia · Alimentação · Transporte · Saúde e Bem-Estar · Educação e Trabalho · Lazer e Tecnologia · Dívidas.

Transações sem categoria ficam com `category_id = NULL` ("Sem categoria") — não há categoria "Outros" no seed.

## 9. Questões em aberto

| # | Questão | Quem responde | Bloqueia? |
|---|---|---|---|
| **Q1** | ✅ **Nubank resolvido:** cartão = CSV, conta = OFX (CSV opcional), PDF descartado. 🟡 **Itaú pendente:** quais formatos a conta e a fatura do cartão exportam (OFX? XLS? só PDF?). | Usuário (baixar arquivos do Itaú) | Só para os adapters do Itaú — Nubank pode começar |
| **Q2** | ✅ Verificado em duas faturas consecutivas: parcela `1/N` vem com a data da compra, parcelas `n ≥ 2` com a data de abertura do ciclo. Competência = mês da data da linha (ver R3). | — | — |
| **Q3** | ✅ Decidida: `conta + external_id` quando o arquivo tem identificador; `hash(conta + data + valor + descrição + ordinal)` quando não tem (ver R2). | — | — |
| **Q4** | ✅ Parcelas futuras gravadas como transações `projetada`, substituídas pela real quando ela chega (ver R10). | Usuário | — |
| **Q5** | ✅ Tolerância de valor ±10%, intervalo de 25 a 35 dias, mínimo de 3 ocorrências (ver R9). | Usuário | — |
| **Q11** | ✅ `installment_group_key` inclui o mês de competência da parcela 1 (derivado de `competência − (n−1)` meses), evitando colisão entre compras parceladas idênticas feitas em meses diferentes. | Usuário | — |
| **Q12** | 🟡 Revisão de arquitetura: `installment_group_key` passa a usar `description_root` + ordinal, sem valor e sem `merchant_key` (R10). Pendente: confirmar com as amostras do Itaú se a ordenação por valor no ordinal é estável quando a 1ª parcela traz o resto dos centavos. **Risco aceito:** com duas compras parceladas idênticas no mesmo mês, se uma for cancelada/antecipada, a outra passa a ter ordinal 1 no arquivo seguinte e cai no grupo errado — afeta só as projetadas e o sinal de revisão, nunca os totais reais. | Usuário (sessão futura, com amostras do Itaú) | Não — modelo aprovado com ressalva |
| **Q6** | ✅ Classificador local ativado a partir de **100 transações revisadas** (valor inicial, configurável; reavaliar medindo acurácia). | Usuário | — |
| **Q7** | ✅ Card incluído (P1, fase 4): mês seguinte ao selecionado, recorrentes pelo último lançamento, inclui conta e cartão (ver R12). | Usuário | — |
| **Q8** | ✅ Lista inicial definida (7 categorias). | Usuário | — |
| **Q9** | ✅ Estorno = despesa com valor negativo, abatendo a categoria do estabelecimento. | Usuário | — |
| **Q10** | ✅ IOF e demais impostos agregados a uma compra herdam a categoria da compra original (ver R4). | Usuário | — |

## 10. Métricas de sucesso

Medidas pelo próprio uso, a partir dos dados do banco local.

**Indicadores de curto prazo (primeiros fechamentos)**
| Métrica | Como medir | Meta | Stretch |
|---|---|---|---|
| Tempo de fechamento mensal | Cronometrar do upload ao dashboard revisado | ≤ 15 min | ≤ 5 min |
| % categorizado automaticamente (mês novo) | Entre as despesas revisadas do mês (`reviewed_at IS NOT NULL`), fração com `category_source != 'manual'` (sugestão confirmada sem alteração) | ≥ 80% | ≥ 95% |
| Arquivos rejeitados indevidamente | Importações com erro de formato conhecido | 0 | 0 |

**Indicadores de longo prazo (3 meses)**
| Métrica | Como medir | Meta |
|---|---|---|
| Fechamentos realizados | Meses consecutivos com importação e revisão concluídas | 3 de 3 |
| Confiabilidade dos totais | Total de despesas de cartão do mês conferido contra a fatura (descontando itens ignorados) | Diferença R$ 0,00 |
| Duplicidades | Transações duplicadas encontradas em conferência | 0 |

## 11. Faseamento

Sem prazo fixo — projeto pessoal. Ordem sugerida, cada fase utilizável por si só:

| Fase | Entregas | Depende de |
|---|---|---|
| **0. Descoberta** | ✅ Nubank analisado; arquitetura e modelo de dados aprovados. Pendente (não bloqueia): amostras do Itaú (Q1) e Q12 | — |
| **1. Importar** | R1, R2, R3, R4, R5 + estrutura do repositório, Alembic, backup automático, teste de independência de ordem | Fase 0 |
| **2. Categorizar e revisar** | R6 (estratégias 1–2), R7 | Fase 1 |
| **3. Dashboard** | R8 | Fase 2 |
| **4. Recorrência e parcelas** | R9, R10, R12 | Fase 3 |
| **5. Categorização avançada** | R11 (classificador local, Gemini opcional) | Fase 2 + histórico revisado |

---

## Anexo A — Formatos de arquivo verificados

Analisados em 2026-09-25 a partir de `samples/` (arquivos reais, **não versionados**). Os exemplos abaixo não contêm dados pessoais.

### A.1 Nubank cartão — CSV ✅
Nome do arquivo: `Nubank_AAAA-MM-DD.csv` (data de **vencimento** da fatura). Uma fatura por arquivo.

```
date,title,amount
2026-08-31,Forneria,"10,06"
2026-08-18,"IOF de ""Anthropic* Claude Sub""","4,00"
2026-08-10,Uber - NuPay,"- 12,93"
2026-08-04,Pagamento recebido,"- 3.317,60"
2026-08-01,Latam Air*0000 - Parcela 4/4,"909,46"
```

| Aspecto | Observado |
|---|---|
| Detecção | Cabeçalho exato `date,title,amount` |
| Encoding / separador | UTF-8, vírgula; campos com aspas quando necessário (aspas internas duplicadas `""`) |
| Data | ISO `AAAA-MM-DD` |
| Valor | Formato brasileiro entre aspas: milhar `.`, decimal `,`, negativo como `"- 12,93"` (**com espaço** após o sinal) |
| Sinal | **Positivo = compra**; negativo = estorno ou pagamento da fatura |
| Identificador | **Nenhum** → dedup por hash + ordinal (R2) |
| Conta | Não identifica o cartão → uma conta "Nubank cartão" fixa |
| Parcelas | Sufixo ` - Parcela n/N` no título; parcela `1/N` com a data da compra; parcelas `n ≥ 2` datadas na abertura do ciclo da fatura (dia 01). Sequência conferida entre as faturas de jul e ago/2026 (ex.: `Latam Air 3/4 → 4/4`, `Pag*Steam 1/3 → 2/3`) |
| Mesmo estabelecimento, parcelamentos distintos | Ocorre: duas linhas `Pag*Steam - Parcela 3/3` no mesmo dia com valores diferentes (13,31 e 7,94) → são compras diferentes, distinguidas pelo `ordinal` do `installment_group_key` (R10) |
| IOF | Linha separada `IOF de "<título original>"` |
| Duplicatas legítimas | Presentes (mesma data, título e valor) |

### A.2 Nubank conta — OFX ✅ (preferencial)
Nome: `NU_<conta>_<DDMMMAAAA>_<DDMMMAAAA>.ofx` (período do extrato).

| Aspecto | Observado |
|---|---|
| Formato | OFX 1.02 (SGML, tags sem fechamento obrigatório), `ENCODING:UTF-8` |
| Detecção | Cabeçalho `OFXHEADER:100`; banco por `<FID>260</FID>` / `<BANKID>0260</BANKID>` |
| Conta | `<ACCTID>` + `<ACCTTYPE>CHECKING</ACCTTYPE>` → identifica a conta automaticamente |
| Data | `<DTPOSTED>AAAAMMDDhhmmss[-3:BRT]` |
| Valor | `<TRNAMT>` com ponto decimal; **negativo = saída** |
| Tipo | `<TRNTYPE>` `DEBIT` / `CREDIT` |
| Identificador | `<FITID>` (UUID) → `external_id` |
| Descrição | `<MEMO>` — mesmo texto do CSV |

### A.3 Nubank conta — CSV (opcional, P1)
```
Data,Valor,Identificador,Descrição
02/09/2026,-4350.29,<uuid>,Pagamento de fatura
02/09/2026,-10.07,<uuid>,Compra no débito - POSTO RUI BARBOSA
```
Data `DD/MM/AAAA`, valor com ponto decimal e negativo = saída, `Identificador` = mesmo UUID do `FITID` do OFX (importar OFX e CSV do mesmo período não duplica).

### A.4 Nubank conta — PDF ❌ não suportado
Mesmas transações do OFX, em layout de relatório (descrições quebradas em várias linhas, totais por dia). Não acrescenta informação.

### A.5 Padrões de descrição da conta Nubank
| Descrição (início) | Tratamento padrão |
|---|---|
| `Pagamento de fatura` | `ignorar / pagamento_fatura` |
| `Compra no débito - <ESTABELECIMENTO>` | `despesa`, merchant = estabelecimento |
| `Transferência enviada pelo Pix - <NOME> - ...` | `despesa` sem categoria (ou `transferencia_interna` se `<NOME>` = titular) |
| `Transferência recebida pelo Pix ...`, `Transferência Recebida ...`, `Crédito em conta` | `ignorar / receita` (todo crédito) |

### A.6 Itaú 🟡 pendente
Sem amostras. Necessário: extrato da conta e fatura do cartão, idealmente em OFX ou XLS.
