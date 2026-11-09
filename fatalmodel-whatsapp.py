#!/usr/bin/env python3
"""
Visita cada URL de perfil do fatalmodel.com (gerado por fatalmodel-listagem.py)
e extrai o número de WhatsApp embutido no payload __NUXT_DATA__ da página,
montando o link pronto de api.whatsapp.com/send.

Uso:
    python3 fatalmodel-whatsapp.py <entrada.csv> --saida <saida.csv>

O CSV de entrada precisa ter as colunas: ad_id, url (gerado por fatalmodel-listagem.py).
O CSV de saída adiciona: nome, whatsapp_numero, whatsapp_link
"""
import argparse
import csv
import json
import re
import sys
import time
import urllib.request

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "pt-BR,pt-PT;q=0.9,pt;q=0.8,en;q=0.7",
    "user-agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "Cookie": "i18n_region=BR",
}

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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("entrada", help="CSV de entrada com colunas ad_id, url")
    parser.add_argument("--saida", required=True, help="CSV de saída")
    parser.add_argument("--espera", type=float, default=1.5, help="segundos entre requisições (padrão: 1.5)")
    args = parser.parse_args()

    with open(args.entrada, newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    resultado = []
    for i, linha in enumerate(linhas, 1):
        ad_id = linha["ad_id"]
        url = linha["url"]
        print(f"[{i}/{len(linhas)}] {url}", file=sys.stderr)

        try:
            html = fetch_profile(url)
            numero, nome = extract_whatsapp(html)
        except Exception as exc:
            print(f"  erro: {exc}", file=sys.stderr)
            numero, nome = None, None

        link = montar_link_whatsapp(numero, ad_id, nome) if numero else None

        resultado.append({
            **linha,
            "nome": nome,
            "whatsapp_numero": numero,
            "whatsapp_link": link,
        })

        if numero:
            print(f"  ok: {nome} -> {numero}", file=sys.stderr)
        else:
            print(f"  não achou número de whatsapp", file=sys.stderr)

        if i < len(linhas):
            time.sleep(args.espera)

    campos = list(linhas[0].keys()) + ["nome", "whatsapp_numero", "whatsapp_link"]
    with open(args.saida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(resultado)

    print(f"salvo em {args.saida} ({len(resultado)} linhas)", file=sys.stderr)


if __name__ == "__main__":
    main()
