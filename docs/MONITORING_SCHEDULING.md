# Agendamento do monitoramento no Windows

O monitoramento é executado por um comando único que roda **um ciclo** e termina.
A periodicidade é fornecida pelo **Agendador de Tarefas do Windows** — não há
processo residente nem dependência de uma sessão do modelo aberta.

## Comando

Na raiz do repositório:

```powershell
python -m radar monitor --db .\data\radar.sqlite3
```

Opções:

- `--analyze` — após registrar uma versão nova, extrai blocos e propostas (nunca valida nada automaticamente).
- `--db PATH` — caminho do banco SQLite (obrigatório).

O comando exige o esquema documental já migrado. Na primeira vez:

```powershell
New-Item -ItemType Directory -Path .\data -Force
python -m radar documents-migrate --db .\data\radar.sqlite3
python -m radar monitor --db .\data\radar.sqlite3
```

O resumo do ciclo é impresso em JSON. Estados possíveis do ciclo: `concluido`,
`parcial`, `falhou`, `interrompido`. Uma falha de fonte é registrada sem apagar o
último resultado válido.

## Agendar pelo Agendador de Tarefas (interface)

1. Abra **Agendador de Tarefas** → **Criar Tarefa**.
2. **Geral**: nome "Radar de Concursos — Monitoramento"; marque "Executar estando
   o usuário conectado ou não" somente se souber a senha da conta.
3. **Disparadores**: Novo → diariamente, repetir a cada **6 horas** por tempo
   indefinido (ou a frequência desejada).
4. **Ações**: Novo → Iniciar um programa.
   - Programa/script: `C:\caminho\do\python.exe` (o do venv do projeto, ex.: `.\.venv\Scripts\python.exe`).
   - Adicionar argumentos: `-m radar monitor --db "C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3"`
   - Iniciar em: `C:\Users\anton\OneDrive\Desktop\radar-de-concursos`
5. **Condições**: marque "Iniciar a tarefa somente se o computador estiver em CA"
   desmarcado, se quiser execução mesmo na bateria. Marque **"Executar tarefa
   assim que possível após uma inicialização perdida"** para recuperar após
   reinício.
6. **Configurações**: "Se a tarefa falhar, reiniciar a cada ..." opcional.

## Agendar por linha de comando (`schtasks`)

Substitua os caminhos pelos reais. Este comando **cria** a tarefa; ele não é
executado por este projeto automaticamente.

```powershell
schtasks /Create /TN "Radar de Concursos - Monitoramento" /SC HOURLY /MO 6 /F `
  /TR "\"C:\Users\anton\OneDrive\Desktop\radar-de-concursos\.venv\Scripts\python.exe\" -m radar monitor --db \"C:\Users\anton\OneDrive\Desktop\radar-de-concursos\data\radar.sqlite3\""
```

Executar uma vez agora (verificação manual do agendamento):

```powershell
schtasks /Run /TN "Radar de Concursos - Monitoramento"
```

Remover o agendamento:

```powershell
schtasks /Delete /TN "Radar de Concursos - Monitoramento" /F
```

## Recuperação após reinicialização

A recuperação é responsabilidade do Agendador: a tarefa volta a rodar no próximo
disparador. O próprio comando também recupera estado: se um ciclo ficou
`em_andamento` (interrompido por desligamento), o ciclo seguinte o marca como
`interrompido` antes de abrir o novo, sem apagar dados anteriores.

## Limites e cuidados

- Não habilite tarefas que gerem cobranças ou downloads ilimitados sem revisar a
  frequência. Cada ciclo rebaixa os documentos conhecidos para comparação; em
  fontes com PDF grande, aumente o intervalo.
- O monitoramento respeita as regras de acesso das fontes oficiais; não contorna
  bloqueios e não faz coleta em massa.
- A ausência de um link numa consulta isolada **não** é prova de remoção; a
  cobertura permanece "não verificada" até auditoria humana explícita.
