# Pesquisa — Fase 36: operação, revalidação e carteira de oportunidades

Data da consulta: **2026-10-18**. Objetivo: comparar padrões e ferramentas para monitorar
mudanças, registrar proveniência e validar dados, sem adotar dependência nova.

## 1. Monitoramento de mudanças e alertas

### changedetection.io

- URL: https://github.com/dgtlmoon/changedetection.io/
- Documentação da API: https://changedetection.io/docs/api_v1/index.html
- Instalação via pip: https://www.mintlify.com/dgtlmoon/changedetection.io/installation/pip
- Licença: Apache 2.0. Python ≥ 3.10. ~35 mil estrelas.
- O que oferece: watches por URL, agendamento por fuso, diff de texto/PDF, checksum de PDF,
  notificações via Apprise, API REST.
- O que foi considerado: usar o projeto como motor externo de monitoramento, em vez do
  `ops-ciclo` próprio.
- Decisão: **não adotar**. O Radar já tem monitoramento, orçamento, política de fontes e
  histórico de versões integrados ao SQLite; trocar o motor exigiria um segundo banco/serviço
  e duplicaria a lógica de política. O conceito aproveitado é o **checksum do documento**
  (já usado em `versoes_documento.sha256` e agora na revalidação).

### Padrão adotado

Revalidar não é "detectar mudança" genérica: é comparar o hash do documento oficial já
conhecido com o hash servido agora. Se mudou, a nova versão é do ciclo de monitoramento; se
não mudou, o prazo continua candidato. Nada é sobrescrito.

## 2. Proveniência e auditoria

### W3C PROV

- PROV-DM: https://www.w3.org/TR/prov-dm/ (Recomendação W3C, 30/04/2013)
- PROV-O: https://www.w3.org/TR/prov-o/ (Recomendação W3C, 30/04/2013)
- Modelo: entidades, atividades, agentes, derivações, bundles.
- Decisão: **não adotar RDF/OWL**. O modelo do Radar já guarda o essencial (documento →
  versão → bloco → evidência → proposta → decisão → autor → data) e o SQLite é a fonte de
  verdade. A fase apenas reforça a regra: toda verificação registra **quem, quando, o quê e
  com que resultado**, sem conteúdo.

### OpenLineage

- https://openlineage.io/docs/
- Especificação: https://github.com/OpenLineage/OpenLineage/blob/main/spec/OpenLineage.md
- Modelo: job, run, dataset, facets; eventos START/COMPLETE.
- Decisão: **não adotar**. É orientado a pipelines de dados (Airflow/Spark/dbt) e exigiria
  infraestrutura de eventos. O equivalente local já existe em `ciclos_monitoramento`,
  `eventos_documento` e na linha do tempo.

## 3. Qualidade e cobertura de dados

Abordagens examinadas conceitualmente (sem adoção): validação declarativa por expectativas
(Great Expectations/Soda) e métricas de completude por campo. O Radar já mede cobertura por
estado documental e por campo decisivo; a Fase 36 acrescenta **prontidão explicável** em vez
de um score único, porque o problema não é "qualidade média", é "o que impede decidir".

## 4. Fontes oficiais e políticas

Consultadas no catálogo interno da Fase 29 (evidência registrada em 2026-10-17):

| Fonte | ID | Permissão para documento | Evidência |
|---|---|---|---|
| FGV Conhecimento | `fgv-conhecimento` | `persistencia_permitida` | https://conhecimento.fgv.br/concursos |
| Quadrix | `quadrix` | `persistencia_permitida` | https://www.quadrix.org.br/ |

A revalidação usa a mesma decisão de política (`source_policy.decision(source, "documento")`),
o mesmo orçamento e o mesmo limite de documento do pipeline. Não há API paga, crédito ou
consulta massiva.

## 5. O que foi rejeitado

- **Motor externo de monitoramento** (changedetection.io): duplicaria banco, política e
  histórico.
- **RDF/PROV ou OpenLineage**: infraestrutura desproporcional ao SQLite local.
- **Score único de oportunidade**: esconde diferenças entre documentação oficial,
  elegibilidade formal, reserva e prazo.
- **Revalidar todos os 110 prazos**: coleta massiva; a fase prioriza futuros com impacto na
  candidatura e registra quantos ficaram pendentes.
- **Baixar e substituir a versão quando o hash muda**: a nova versão é do ciclo de
  monitoramento; a revalidação só registra o fato.

## 6. Decisões de implementação derivadas

1. Comparação por sha256 do documento oficial (padrão do changedetection.io para PDF).
2. Registro append-only com autor/data/resultado (princípio de proveniência do PROV, sem RDF).
3. `dry_run` sem rede, para simulação honesta.
4. Redirecionamento só no mesmo host e HTTPS, para não aplicar política a um destino diferente.
5. Prontidão por estado + motivos, em vez de score.
