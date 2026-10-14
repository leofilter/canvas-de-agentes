# Canvas de agentes

Uma skill para o Claude Code que monta, no canvas do Maestri, uma equipe de agentes organizada:

- **um maestro no centro** — o único com quem você fala;
- **um executor por frente de trabalho** (projeto, cliente ou área), cada um com papel definido e a pasta certa;
- **um fichário "Governança"** com o mapa da equipe e as regras de delegação.

Você responde 4 perguntas, confere o plano e diz "pode montar".

## Instalar

Precisa do Maestri e do Claude Code.

**Windows (PowerShell):**

```powershell
git clone https://github.com/leofilter/canvas-de-agentes "$env:TEMP\canvas-de-agentes"
Copy-Item "$env:TEMP\canvas-de-agentes\canvas-de-agentes" "$env:USERPROFILE\.claude\skills\" -Recurse -Force
```

**macOS / Linux:**

```bash
git clone https://github.com/leofilter/canvas-de-agentes /tmp/canvas-de-agentes
mkdir -p ~/.claude/skills && cp -r /tmp/canvas-de-agentes/canvas-de-agentes ~/.claude/skills/
```

## Usar

1. Abra o Maestri e um terminal com o Claude Code em **Modo Maestro**.
2. Digite `/canvas-de-agentes` (ou "monte meu canvas de agentes").
3. Responda as perguntas, confira a tabela e diga "pode montar".

Cada executor é um terminal novo com um agente rodando: ele usa a sua assinatura ou a sua cota.

## O que ela não faz

- **Não move as caixas com o Maestri aberto.** O aplicativo não aceita comando de posição. A skill desenha
  **3 arranjos com os nomes da sua equipe**, você escolhe um (ou pede outros três), fecha o Maestri, roda um
  comando e abre de novo já com tudo no lugar: maestro à esquerda, uma área colorida por frente, estante à direita.
  Esse passo precisa de Python 3, faz cópia de segurança antes e tem `desfazer`. Foi testado no Windows.
- **Não apaga nada.** Não remove terminal, nota nem papel.
- **Não guarda memória entre sessões** nem organiza o seu trabalho com clientes. Ela organiza os agentes.

## E o trabalho que os agentes fazem?

A skill deixa cada agente sabendo de que frente cuida. Regras, modelos de documento e procedimentos por área
(contabilidade, direito, engenharia, marketing, desenvolvimento e outras) são o que o
**[PRAXIS](https://praxis.filterpro.dev.br)** entrega para a IA que você já usa.

## Aviso

Projeto independente, de Leonardo Filter Friedrich ([FilterPro](https://filterpro.dev.br) — ferramentas sob medida, automação e [visibilidade nas IAs](https://filterpro.dev.br/visibilidade-nas-ias)). Não é afiliado ao Maestri nem à Anthropic, e
não distribui código de nenhum dos dois: só usa a linha de comando `maestri` que já vem com o aplicativo.

Licença: MIT.
