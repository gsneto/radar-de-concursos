# Pesquisa — Fase 39: identidade por código, escolaridade e elegibilidade formal

Data da consulta: **2026-10-18**. Objetivo: resolver os problemas concretos da fase sem
dependência nova.

## 1. Entity resolution e aliases de cargo

O projeto já tem `role_identity` (F35): pontuação estrutural (nome, código, prefixo,
especialidade) e decisão humana append-only. A fase **não** cria outro resolvedor.

O que faltava era a **junção entre representações do mesmo código**: a leitura de formação está
pendurada no rótulo só-código (`"200"`) e a oportunidade no rótulo nomeado
(`"200 … Assistente Administrativo"`). A junção adotada é **exata por código dentro do mesmo
concurso**, com guarda: código repetido entre dois nomes = não juntar.

Alternativas descartadas:

- similaridade textual (proibida pelo projeto como prova de identidade);
- fusão por título-base (perderia código, localidade e vagas — o erro que a fase proíbe).

## 2. Identidade de cargo versus código de vaga

Referência conceitual: em concursos, o **código** é a chave de inscrição; o título-base é
apenas o nome comercial. Dois códigos com o mesmo título em municípios diferentes são
**opções distintas** (o candidato escolhe uma). Por isso o modelo tem três níveis:

- família (título-base) — leitura de apoio;
- cargo/código — identidade individual;
- localidade — opção de inscrição.

A família nunca transfere dado; a matriz expõe `familia`, `codigo` e `localidade` separadamente.

## 3. Escolaridade mínima versus curso específico

Abordagens comparadas:

- **Modelo de linguagem** para interpretar o requisito. Descartado: não auditável, não
  reproduzível, exigiria serviço externo.
- **Listas de áreas** (o que existia). Mantido como sinal, mas insuficiente: "direito de
  dirigir" casava "direito"; "área de computação" casava abertura de categoria.
- **Nível + cláusula de área** (adotado): primeiro o **nível** (médio/técnico/superior),
  depois a **área** lida da cláusula ("em …", "nas áreas de …"), com fallback para o formato
  compacto do quadro ("Nível Superior - Direito").

Regra derivada: requisito de nível mínimo **não** é incompatibilidade nem ambiguidade; é
candidato de compatibilidade por nível, declarado como tal.

## 4. Cargos equivalentes distribuídos por municípios

O quadro da Quadrix publica uma linha por código, com a lotação ao final. A extração da
localidade usa a linha já validada (soma das modalidades confere com o total) e lê o município
imediatamente antes da carga horária. Evidência = linha inteira + município, o que mantém a
localidade amarrada ao código (e não a um texto solto).

## 5. Extração de requisitos em tabelas e textos corridos

Mantido o parser de quadro em texto (F38) e o extrator de seções numeradas (F33). A fase
acrescentou apenas a leitura de **localidade** na tabela Quadrix e a junção por código.

## 6. Revisão humana, proveniência e histórico

Mantido o modelo documento → versão → bloco → evidência → proposta → decisão. A ficha de
revisão mostra o valor armazenado e a leitura atual do texto, para que a decisão humana seja
informada. Nenhuma tabela paralela.

## 7. Testes de regressão para sistemas de elegibilidade

Padrão adotado: fixtures determinísticas por tipo de requisito (nível médio, superior sem área,
técnico de TI, técnico de outra área, categoria ampla, graduação específica, licenciatura,
registro profissional) + o caso piloto com sete códigos, cada um com sua localidade. O teste
verifica que não há transferência de vaga entre códigos.

## 8. Fontes

- Página oficial do concurso: `https://quadrix.org.br/informacoes/3049/` (referência externa
  citada na missão; o quadro foi conferido contra o **documento armazenado**).
- Edital armazenado: `anexos-r2.selecao.net.br/uploads/861/concursos/3049/anexos/d9b6bbe8-….pdf`
  (política `persistencia_permitida`).
- Nenhuma coleta nova: a fase usou os documentos e versões já armazenados; a extração nova foi
  aplicada por reprocessamento idempotente.

## 9. O que foi rejeitado

- Fundir 200–206 em um cargo só: perderia código, município, vagas e a escolha do candidato.
- Tratar "CR" ou "-" como zero: inventaria quantidade (mantido da F38).
- Deduzir que 208 aceita bacharelado por ser "de T.I.": o requisito é curso **técnico**;
  virou interpretação humana, não categoria.
- Marcar licenciatura como nível mínimo: um bacharelado não satisfaz licença para lecionar.
- Criar segunda fila de revisão: a matriz complementa a mesa.
