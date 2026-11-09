# Scraper fatalmodel.com — listagem + WhatsApp por cidade

Experimento de 26/08/2026: extrair a listagem completa de anúncios de uma cidade no fatalmodel.com (fotos + link do perfil) e, a partir de cada perfil, o número de WhatsApp já formatado como link `api.whatsapp.com/send`.

## O que foi descoberto

- A API pública `/api/seo/v1/fatal-fans/cards/acompanhantes` **não pagina** — é um widget fixo de até 24 itens (recurso "Fatal Fans", separado da listagem principal). `limit`/`page`/`offset` nela não têm efeito real.
- A listagem real de anúncios por cidade é **renderizada direto no HTML** da página `https://fatalmodel.com/acompanhantes-<cidade>-<uf>`, paginada via `?page=N` (não é scroll infinito puro — a própria página tem `rel="next"` apontando pra `?page=2`, `?page=3`, etc.). O total por cidade fica embutido no HTML (`"total":N`).
- Cada card de anúncio tem um `<div id="listingCard<ad_id>">` com o link do perfil (`href="https://fatalmodel.com/acompanhante/<id>/<slug>"`) e a foto — mas o atributo da foto varia por tipo de card: cards "top/destaque" usam `data-src="'<url>'"` (Vue bind, domínio `files.fatalmodel.com`), cards normais usam `src="<url>"` direto (domínio `fatalmodel.com/cdn-cgi/image/...`).
- O número de WhatsApp de cada perfil **não aparece em texto puro** no HTML — vem embutido no payload serializado `<script data-nuxt-data>` (formato Nuxt "devalue": um array plano onde cada objeto referencia outros elementos por índice numérico). O campo `phone_number_whatsapp` aponta pro índice do array que contém o número (sem o "55" do país). O botão "Chamar no WhatsApp" da página monta o link client-side a partir desse dado — não existe uma chamada de API separada pra revelar o número.

## Scripts

- [`./fatalmodel-listagem.py`](./fatalmodel-listagem.py) — percorre `?page=N` de uma cidade e extrai `ad_id`, `url` do perfil e `foto` de cada anúncio.
  ```bash
  python3 fatalmodel-listagem.py maringa-pr --saida maringa-completo.csv
  ```
- [`./fatalmodel-whatsapp.py`](./fatalmodel-whatsapp.py) — recebe o CSV gerado acima, visita cada perfil e adiciona `nome`, `whatsapp_numero` e `whatsapp_link` (mensagem padrão + link curto `fatal.fm/<ad_id>`).
  ```bash
  python3 fatalmodel-whatsapp.py maringa-completo.csv --saida maringa-completo.csv --espera 1.5
  ```

## Arquivos gerados

- `maringa-completo.csv` — 144 anúncios de Maringá-PR (ad_id, url, foto), sem WhatsApp ainda.
- `maringa-teste5-whatsapp.csv` — amostra de 5 perfis com WhatsApp já extraído, validando o script acima antes de rodar nos 144.

## Status

Testado e validado em 5 perfis (100% de acerto). Ainda não rodado nos 144 completos — pendente decisão do Bruno se/quando rodar em escala (rate-limit de ~1.5s por request, ~144 requests ≈ 4min).
