#!/usr/bin/env python3
"""
Baixa e extrai a listagem de acompanhantes do fatalmodel.com por cidade,
percorrendo as páginas HTML (?page=N) -- não usa a API de "fatal-fans/cards",
que é um recurso separado e limitado a 24 itens.

Uso:
    python3 fatalmodel-listagem.py <slug-cidade> [--paginas N] [--saida arquivo.json]

Exemplo:
    python3 fatalmodel-listagem.py maringa-pr --saida maringa.json
"""
import argparse
import json
import re
import sys
import time
import urllib.request

BASE_URL = "https://fatalmodel.com/acompanhantes-{cidade}"
HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "pt-BR,pt-PT;q=0.9,pt;q=0.8,en;q=0.7",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Cookie": "i18n_region=BR",
}

CARD_START_RE = re.compile(r'<div id="listingCard(?P<ad_id>\d+)"')
URL_RE = re.compile(r'href="(https://fatalmodel\.com/acompanhante/\d+/[a-z0-9-]+)"')
FOTO_RE = re.compile(r':?(?:data-)?src="\'?(https://(?:files\.)?fatalmodel\.com/[^\'"]+\.(?:jpe?g|png|webp))')
TOTAL_RE = re.compile(r'&quot;total&quot;:(\d+)')
CARD_BLOCK_SIZE = 10000  # chars de janela a partir do início do card, suficiente pra achar link+foto sem vazar pro próximo card


def fetch_page(cidade: str, page: int) -> str:
    url = BASE_URL.format(cidade=cidade)
    if page > 1:
        url += f"?page={page}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_cards(html: str) -> list[dict]:
    cards = []
    seen = set()
    starts = list(CARD_START_RE.finditer(html))
    for idx, m in enumerate(starts):
        ad_id = m.group("ad_id")
        if ad_id in seen:
            continue
        block_end = starts[idx + 1].start() if idx + 1 < len(starts) else len(html)
        block_end = min(block_end, m.end() + CARD_BLOCK_SIZE)
        block = html[m.end():block_end]

        url_m = URL_RE.search(block)
        foto_m = FOTO_RE.search(block)
        if not url_m:
            continue

        seen.add(ad_id)
        cards.append({
            "ad_id": ad_id,
            "url": url_m.group(1),
            "foto": foto_m.group(1) if foto_m else None,
        })
    return cards


def extract_total(html: str) -> int | None:
    m = TOTAL_RE.search(html)
    return int(m.group(1)) if m else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cidade", help='slug da cidade, ex: "maringa-pr"')
    parser.add_argument("--paginas", type=int, default=None, help="número máximo de páginas a buscar (padrão: detecta pelo total)")
    parser.add_argument("--saida", default=None, help="arquivo JSON de saída (padrão: stdout)")
    parser.add_argument("--espera", type=float, default=1.0, help="segundos de espera entre requisições (padrão: 1.0)")
    args = parser.parse_args()

    all_cards = []
    seen_ids = set()
    page = 1
    total = None
    max_pages = args.paginas

    while True:
        print(f"buscando página {page}...", file=sys.stderr)
        html = fetch_page(args.cidade, page)

        if total is None:
            total = extract_total(html)
            if total:
                print(f"total anunciado pelo site: {total}", file=sys.stderr)

        cards = extract_cards(html)
        novos = [c for c in cards if c["ad_id"] not in seen_ids]
        for c in novos:
            seen_ids.add(c["ad_id"])
        all_cards.extend(novos)

        print(f"  {len(cards)} cards na página, {len(novos)} novos (total acumulado: {len(all_cards)})", file=sys.stderr)

        if not cards or not novos:
            break
        if max_pages and page >= max_pages:
            break
        if total and len(all_cards) >= total:
            break

        page += 1
        time.sleep(args.espera)

    output = json.dumps(all_cards, ensure_ascii=False, indent=2)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"salvo em {args.saida} ({len(all_cards)} itens)", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
