Diariamente, gere a nova edição da newsletter Clickdata Drops.

1. PESQUISE as 5 principais notícias das últimas 24 horas sobre IA, 
   Tecnologia e Transformação Digital — Brasil e mundo.
   Priorize fontes confiáveis (Stanford HAI, MIT Tech Review, 
   Exame, Valor, TechCrunch, IDC, Gartner).

2. Para cada notícia inclua obrigatoriamente:
   - O link original da fonte
   - Tag de categoria (Mercado, Geopolítica IA, etc.)
   - Botão "→ Ler matéria completa"

3. MONTE o HTML usando o arquivo template.html do repositório
   como base. Mantenha o design exato, substitua apenas 
   o conteúdo editorial e atualize: número da edição, 
   data, stats da semana e seção Perspectiva.

4. SALVE o HTML gerado como `edicoes/ed-[NNN]-[AAAA-MM-DD].html`

5. ENVIE a newsletter via Brevo API:
   - Endpoint: POST https://api.brevo.com/v3/emailCampaigns
   - API Key: []
   - Lista de destinatários: ID da lista []
   - Assunto: "Clickdata Drops #[NNN] — [Data]"
   - Conteúdo: o HTML gerado
   - Agende o envio para as 8h do mesmo dia
