#!/usr/bin/env python3
"""
Raspa o fatalmodel.com de uma cidade: lista os anúncios (todas as páginas) e,
para cada perfil, extrai nome e WhatsApp.

Uso:
    python3 fatalmodel.py <url-ou-slug> [--limite N] [--espera S] [--pasta saidas]

Exemplo:
    python3 fatalmodel.py https://fatalmodel.com/acompanhantes-florianopolis-sc
    python3 fatalmodel.py florianopolis-sc --limite 5      # teste rápido

Gera em saidas/<slug>/ :
    listagem.json   ad_id, url, foto
    listagem.csv    o mesmo, em CSV
    whatsapp.csv    ad_id, url, foto, nome, whatsapp_numero, whatsapp_link
"""
import argparse
import csv
import json
import os
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


NUXT_SCRIPT_RE = re.compile(r'<script[^>]*data-nuxt-data[^>]*>')
PHONE_IDX_RE = re.compile(r'"phone_number_whatsapp":(\d+)')
TITLE_IDX_RE = re.compile(r'"title":(\d+)')

MENSAGEM_PADRAO = (
    "Olá, {nome}! Vi seu perfil na Fatal e gostaria de marcar um atendimento. "
    "Quando você tem disponibilidade?\nhttps://fatal.fm/{ad_id}"
)


def fetch_profile(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_whatsapp(html: str) -> tuple[str | None, str | None]:
    """Retorna (numero_whatsapp, nome) ou (None, None) se não achar."""
    m = NUXT_SCRIPT_RE.search(html)
    if not m:
        return None, None
    start = m.end()
    end = html.find("</script>", start)
    payload_text = html[start:end]

    phone_idx_m = PHONE_IDX_RE.search(payload_text)
    title_idx_m = TITLE_IDX_RE.search(payload_text)
    if not phone_idx_m:
        return None, None

    arr = json.loads(payload_text)
    numero = arr[int(phone_idx_m.group(1))]
    nome = arr[int(title_idx_m.group(1))] if title_idx_m else None

    numero = str(numero) if numero else None
    return numero, nome


def montar_link_whatsapp(numero: str, ad_id: str, nome: str) -> str:
    from urllib.parse import quote
    texto = MENSAGEM_PADRAO.format(nome=nome or "", ad_id=ad_id)
    return f"https://api.whatsapp.com/send?phone=55{numero}&text={quote(texto)}"



def listar(cidade, espera, limite):
    todos, vistos, page, total = [], set(), 1, None
    while True:
        print(f"listando página {page}...", file=sys.stderr)
        html = fetch_page(cidade, page)
        if total is None:
            total = extract_total(html)
            if total:
                print(f"total anunciado pelo site: {total}", file=sys.stderr)
        novos = [c for c in extract_cards(html) if c["ad_id"] not in vistos]
        for c in novos:
            vistos.add(c["ad_id"])
        todos.extend(novos)
        if not novos or (limite and len(todos) >= limite) or (total and len(todos) >= total):
            break
        page += 1
        time.sleep(espera)
    return todos[:limite] if limite else todos


def slug_da_entrada(valor: str) -> str:
    """Aceita a URL completa ou só o slug e devolve o slug (ex: florianopolis-sc)."""
    m = re.search(r"acompanhantes-([a-z0-9-]+)", valor)
    return m.group(1) if m else valor.strip().strip("/")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("cidade", help="URL da cidade no fatalmodel (ou o slug, ex: florianopolis-sc)")
    p.add_argument("--pasta", default="saidas", help="pasta base de saída (padrão: saidas)")
    p.add_argument("--limite", type=int, default=None, help="processa só os N primeiros anúncios (teste)")
    p.add_argument("--espera", type=float, default=3.0, help="segundos entre requisições (padrão: 3.0)")
    args = p.parse_args()

    slug = slug_da_entrada(args.cidade)
    pasta = os.path.join(args.pasta, slug)
    os.makedirs(pasta, exist_ok=True)

    anuncios = listar(slug, args.espera, args.limite)

    # 1) listagem pura (JSON + CSV)
    with open(os.path.join(pasta, "listagem.json"), "w", encoding="utf-8") as f:
        json.dump(anuncios, f, ensure_ascii=False, indent=2)
    with open(os.path.join(pasta, "listagem.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ad_id", "url", "foto"])
        w.writeheader()
        w.writerows(anuncios)
    print(f"listagem salva em {pasta}/ ({len(anuncios)} anúncios)", file=sys.stderr)

    # 2) perfis -> WhatsApp
    resultado = []
    for i, a in enumerate(anuncios, 1):
        print(f"[{i}/{len(anuncios)}] {a['url']}", file=sys.stderr)
        try:
            numero, nome = extract_whatsapp(fetch_profile(a["url"]))
        except Exception as exc:
            print(f"  erro: {exc}", file=sys.stderr)
            numero, nome = None, None
        link = montar_link_whatsapp(numero, a["ad_id"], nome) if numero else None
        resultado.append({**a, "nome": nome, "whatsapp_numero": numero, "whatsapp_link": link})
        if i < len(anuncios):
            time.sleep(args.espera)

    campos = ["ad_id", "url", "foto", "nome", "whatsapp_numero", "whatsapp_link"]
    saida = os.path.join(pasta, "whatsapp.csv")
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(resultado)
    ok = sum(1 for r in resultado if r["whatsapp_numero"])
    print(f"salvo em {saida} ({len(resultado)} linhas, {ok} com WhatsApp)", file=sys.stderr)


if __name__ == "__main__":
    main()
