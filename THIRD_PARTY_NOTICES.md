# Avisos de terceiros (third-party notices)

Este projeto inclui código **adaptado** de projetos open source. As licenças e atribuições
originais são preservadas abaixo, conforme exigido.

## estudo-organizado

- Origem: https://github.com/matheussilva421/estudo-organizado
- Commit analisado: `eb8cc6cf`
- Licença: MIT
- Código adaptado (JS → Python) em `radar/study.py`: `revision_dates`, `pending_revisions`,
  `content_progress`, `total_study_seconds`, `minutes_by_discipline`, `elapsed_seconds`.
- Modificações: reescrito em Python puro; entradas por parâmetro (sem estado global/DOM);
  sem cache global; `adiamentos` é limitado a ``>= 0`` (o original permitia deslocamento
  negativo); datas tratadas como UTC/`date` puro (o original usava datas locais do navegador);
  acrescentado `capped_elapsed` (teto de 24 h) que **não** existe no original. Comportamento
  preservado nos demais pontos e coberto por `tests/test_study.py`.

```
MIT License

Copyright (c) 2026 Matheus Silva

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## smart-student-productivity-dashboard

- Origem: https://github.com/remoshan/smart-student-productivity-dashboard
- Commit analisado: `39f348c0`
- Licença: MIT
- Uso: apenas a **ideia** do ciclo Pomodoro (foco/pausa curta/pausa longa) foi reimplementada
  no cronômetro próprio; nenhum arquivo foi copiado.

```
MIT License

Copyright (c) 2026 Francis Remoshan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Projetos avaliados e **não** utilizados

Os repositórios `track-concursos` (licença proprietária), `Study-Planner`, `banco-provas`,
`Banco-Questoes` e `api-concursos-publicos` (sem arquivo de licença) **não** tiveram código
copiado, por não autorizarem reutilização. `buscar-concursos` (Apache-2.0) foi avaliado e não
teve código copiado por incompatibilidade de stack. Detalhes em
`docs/superpowers/specs/2026-10-16-study-platform-open-source-mining.md`.
