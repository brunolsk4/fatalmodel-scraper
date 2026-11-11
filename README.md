# Scraper fatalmodel.com — listagem + WhatsApp por cidade

**Objetivo do projeto:** raspar (scraping) os números de WhatsApp das acompanhantes anunciadas no fatalmodel.com, cidade por cidade. O resultado é um CSV com nome, link do perfil e link `api.whatsapp.com/send` de cada anúncio.

> Os números são dados pessoais. Os CSVs gerados ficam fora do repositório (`.gitignore`). Uso e armazenamento devem respeitar a LGPD e os termos do site.

Experimento de 26/08/2026: extrair a listagem completa de anúncios de uma cidade no fatalmodel.com (fotos + link do perfil) e, a partir de cada perfil, o número de WhatsApp já formatado como link `api.whatsapp.com/send`.

## O que foi descoberto

- A API pública `/api/seo/v1/fatal-fans/cards/acompanhantes` **não pagina** — é um widget fixo de até 24 itens (recurso "Fatal Fans", separado da listagem principal). `limit`/`page`/`offset` nela não têm efeito real.
- A listagem real de anúncios por cidade é **renderizada direto no HTML** da página `https://fatalmodel.com/acompanhantes-<cidade>-<uf>`, paginada via `?page=N` (não é scroll infinito puro — a própria página tem `rel="next"` apontando pra `?page=2`, `?page=3`, etc.). O total por cidade fica embutido no HTML (`"total":N`).
- Cada card de anúncio tem um `<div id="listingCard<ad_id>">` com o link do perfil (`href="https://fatalmodel.com/acompanhante/<id>/<slug>"`) e a foto — mas o atributo da foto varia por tipo de card: cards "top/destaque" usam `data-src="'<url>'"` (Vue bind, domínio `files.fatalmodel.com`), cards normais usam `src="<url>"` direto (domínio `fatalmodel.com/cdn-cgi/image/...`).
- O número de WhatsApp de cada perfil **não aparece em texto puro** no HTML — vem embutido no payload serializado `<script data-nuxt-data>` (formato Nuxt "devalue": um array plano onde cada objeto referencia outros elementos por índice numérico). O campo `phone_number_whatsapp` aponta pro índice do array que contém o número (sem o "55" do país). O botão "Chamar no WhatsApp" da página monta o link client-side a partir desse dado — não existe uma chamada de API separada pra revelar o número.

## Uso (script unificado)

[`./fatalmodel.py`](./fatalmodel.py) faz tudo em um passo: recebe a URL da cidade, lista todos os anúncios e visita cada perfil pra extrair nome e WhatsApp.

```bash
python3 fatalmodel.py https://fatalmodel.com/acompanhantes-florianopolis-sc
python3 fatalmodel.py florianopolis-sc --limite 5     # teste rápido (5 primeiros)
```

- Aceita a **URL completa** ou só o **slug** (`cidade-uf`, igual aparece na URL do site depois de `acompanhantes-`).
- Opções: `--limite N` (processa só os N primeiros), `--espera S` (segundos entre requisições, padrão **3.0**), `--pasta` (base de saída, padrão `saidas`).
- Só Python 3.10+, sem dependências externas.

Saída em `saidas/<slug>/`:

| Arquivo | Conteúdo |
|---|---|
| `listagem.json` | `ad_id`, `url`, `foto` de cada anúncio |
| `listagem.csv` | o mesmo, em CSV |
| `whatsapp.csv` | tudo acima + `nome`, `whatsapp_numero`, `whatsapp_link` (mensagem padrão + link curto `fatal.fm/<ad_id>`) |

Perfil que falha ou não tem número sai com os campos vazios e o script segue. No fim mostra quantos vieram com WhatsApp. O `whatsapp.csv` só é gravado ao final da execução.

## O que melhoramos (11/11/2026)

- **Um script só**: `fatalmodel.py` substitui o fluxo em duas etapas (`fatalmodel-listagem.py` + `fatalmodel-whatsapp.py`).
- **Entrada por URL**: não precisa mais extrair o slug na mão.
- **Saída organizada**: uma pasta por cidade, com listagem em JSON/CSV e o CSV final de WhatsApp, sem risco de sobrescrever arquivo de outra cidade.
- **Fim da incompatibilidade de formato**: antes a listagem gravava JSON (mesmo com nome `.csv` no exemplo do README) e o script de WhatsApp lia CSV.
- **Delay maior**: padrão de 3 s entre requisições (antes 1 s na listagem e 1,5 s nos perfis), mais seguro contra rate-limit/bloqueio. Florianópolis (384 anúncios) leva ~20 min.
- **`.gitignore`** passou a cobrir `saidas/` e `*.json`, além de `*.csv`.

## Scripts antigos (ainda na pasta)

- [`./fatalmodel-listagem.py`](./fatalmodel-listagem.py) — só a listagem (grava JSON).
- [`./fatalmodel-whatsapp.py`](./fatalmodel-whatsapp.py) — recebe CSV com `ad_id,url` e adiciona nome/WhatsApp.

## Arquivos gerados em testes anteriores

- `maringa-completo.csv` — 144 anúncios de Maringá-PR (ad_id, url, foto), sem WhatsApp.
- `maringa-teste5-whatsapp.csv` — amostra de 5 perfis de Maringá com WhatsApp.
- `florianopolis.json` / `florianopolis.csv` / `floripa-teste*.csv` — listagem de Florianópolis (384 anúncios) e testes de 5 perfis.

## Status

- Validado em 5 perfis de Maringá e 5 de Florianópolis (100% de acerto) e com o script unificado em 2 perfis de Florianópolis.
- Ainda não rodado em escala (Maringá completa, Florianópolis completa) — pendente decisão do Bruno.
