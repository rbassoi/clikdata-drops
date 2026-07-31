# Clikdata Drops — Instruções para Claude

## Visão geral
Newsletter de IA, Tecnologia e Transformação Digital.
Cada edição é um arquivo HTML gerado a partir do `template.html`.

## Fluxo completo de publicação

Execute **todos os passos abaixo** em toda nova edição, sem precisar de confirmação:

### 1. Determinar número da edição
- Verificar o maior número em `edicoes/` e incrementar +1.
- Formato do arquivo: `edicoes/ed-NNN-AAAA-MM-DD.html`

### 2. Pesquisar notícias
- Buscar as 5 principais notícias das últimas 48 horas: IA (mundo e Brasil), Tecnologia, Transformação Digital corporativa.
- Fontes prioritárias: Stanford HAI, MIT Technology Review, Exame, Valor Econômico, TechCrunch, IDC, Gartner, Blip.
- Cada notícia deve ter: link original, tag de categoria e botão "→ Ler matéria completa".

### 3. Gerar o HTML
- Abrir `template.html` e substituir: número da edição, data, notícias, stats e seção Perspectiva.
- **Nunca alterar CSS, fontes, cores ou layout do template.**

### 4. Salvar e commitar
```bash
git add edicoes/ed-NNN-AAAA-MM-DD.html
git commit -m "Clickdata Drops #NNN — DD/MM/AAAA"
git push -u origin <branch-atual>
```

### 5. Criar PR e mergear para main (AUTOMÁTICO — sem pedir confirmação)
Após o push, **sempre** executar:
1. Criar PR de `<branch-atual>` → `main` via `mcp__github__create_pull_request`
2. Mergear imediatamente via `mcp__github__merge_pull_request` com `merge_method: merge`

O merge em `main` dispara automaticamente o GitHub Actions workflow
(`.github/workflows/deploy-newsletter.yml`) que cria e dispara a campanha no Brevo.

### 6. Em caso de erro na API ou no push
- Registrar em `logs/erro-AAAA-MM-DD.txt` com: endpoint, HTTP status, mensagem e ação recomendada.
- Commitar e subir o log junto com a edição.

## Estrutura do repositório
```
template.html                  ← template base (nunca alterar)
edicoes/
  ed-001-2026-05-06.html
  ed-002-2026-05-07.html
  ...
logs/
  erro-AAAA-MM-DD.txt          ← erros de API (Brevo, GitHub)
.github/
  workflows/
    deploy-newsletter.yml      ← CI/CD: cria e dispara campanha Brevo ao mergear em main
```

## Secrets necessários no repositório GitHub
- `CLIKER_API_KEY` — chave da API CLIKER (Settings → Secrets and variables → Actions)

## Importante
- O disparo da campanha Cliker **não é feito diretamente deste ambiente** (proxy de saída bloqueado).
- O envio acontece via GitHub Actions após o merge em `main`.
- Nunca alterar o design do template.
- Sempre incrementar o número da edição.
- Sempre incluir links das fontes nas notícias.
