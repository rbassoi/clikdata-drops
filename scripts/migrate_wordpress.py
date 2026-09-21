#!/usr/bin/env python3
"""
Publica/atualiza edições do Clikdata Drops (edicoes/*.html) como posts no
WordPress (drops.clikdata.com.br), preservando o design original de cada
edição via <iframe src="data:text/html;base64,...">  — sem depender de
upload de mídia .html (bloqueado por padrão no WP), sem depender do CSS
do tema, e sem enviar HTML bruto no corpo da requisição (evita bloqueios
de firewalls tipo Mod_Security, que tendem a barrar payloads com tags
<style>/<script> literais).

Idempotente: mantém um manifesto (wp-migration-state.json) na raiz do repo
com o mapeamento edição -> post_id/post_url/content_hash. Uma edição só é
recriada no WP se o conteúdo do HTML mudou (hash diferente) — caso
contrário é pulada (create) ou atualizada (update) só quando necessário.

Uso:
  python3 scripts/migrate_wordpress.py                # processa todas as edições em edicoes/
  python3 scripts/migrate_wordpress.py edicoes/ed-102-2026-09-17.html   # processa só uma

Variáveis de ambiente obrigatórias:
  WP_BASE_URL       ex: https://drops.clikdata.com.br
  WP_USER           usuário WordPress real (ex: rbassoi) — o "nome" dado à
                    Application Password é só um rótulo, não um usuário
  WP_APP_PASSWORD   Application Password gerado no WP (com espaços, ok)
"""
import base64
import glob
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

import requests

STATE_FILE = "wp-migration-state.json"
EDICOES_GLOB = "edicoes/ed-*.html"
FILENAME_RE = re.compile(r"ed-(\d+)-(\d{4}-\d{2}-\d{2})\.html$")

IFRAME_TEMPLATE = """<!-- wp:html -->
<div class="clikdata-drops-edicao" style="max-width:760px;margin:0 auto;">
<iframe
  src="data:text/html;charset=utf-8;base64,{b64}"
  title="{title}"
  loading="lazy"
  style="width:100%;height:2400px;border:0;display:block;"
  sandbox="allow-popups allow-popups-to-escape-sandbox allow-same-origin"
></iframe>
</div>
<!-- /wp:html -->"""


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def parse_filename(path):
    m = FILENAME_RE.search(os.path.basename(path))
    if not m:
        return None, None
    num, data = m.group(1), m.group(2)
    return int(num), data


def wp_session():
    user = os.environ["WP_USER"]
    app_password = os.environ["WP_APP_PASSWORD"]
    base_url = os.environ["WP_BASE_URL"].rstrip("/")
    s = requests.Session()
    s.auth = (user, app_password)
    s.headers.update({"Content-Type": "application/json"})
    return s, base_url


def build_post_payload(num, data_iso, raw_html):
    data_pt = datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    title = f"Clikdata Drops #{num:03d} — {data_pt}"
    b64 = base64.b64encode(raw_html.encode("utf-8")).decode("ascii")
    content = IFRAME_TEMPLATE.format(b64=b64, title=html.escape(title, quote=True))
    return {
        "title": title,
        "slug": f"clikdata-drops-{num:03d}",
        "status": "publish",
        "date": f"{data_iso}T08:00:00",
        "content": content,
        "excerpt": f"Edição #{num:03d} da newsletter Clikdata Drops — {data_pt}.",
    }


def upsert_post(session, base_url, payload, existing_post_id):
    if existing_post_id:
        url = f"{base_url}/wp-json/wp/v2/posts/{existing_post_id}"
        resp = session.post(url, json=payload, timeout=60)
    else:
        url = f"{base_url}/wp-json/wp/v2/posts"
        resp = session.post(url, json=payload, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WP API {resp.status_code} em {url}: {resp.text[:500]}")
    return resp.json()


def main():
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    files = args if args else sorted(glob.glob(EDICOES_GLOB))
    if not files:
        print("Nenhuma edição encontrada.")
        return

    state = load_state()
    session, base_url = wp_session()

    created, updated, skipped, failed = 0, 0, 0, 0

    for path in files:
        num, data_iso = parse_filename(path)
        if num is None:
            print(f"⚠️  Ignorando (nome fora do padrão): {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            raw_html = f.read()
        content_hash = hashlib.sha256(raw_html.encode("utf-8")).hexdigest()

        key = os.path.basename(path)
        entry = state.get(key)

        if entry and entry.get("content_hash") == content_hash:
            skipped += 1
            continue

        payload = build_post_payload(num, data_iso, raw_html)

        try:
            result = upsert_post(session, base_url, payload, entry.get("post_id") if entry else None)
        except Exception as e:
            print(f"❌ Falha em {key}: {e}")
            failed += 1
            continue

        state[key] = {
            "post_id": result["id"],
            "post_url": result.get("link"),
            "content_hash": content_hash,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }

        if entry:
            updated += 1
            print(f"🔄 Atualizado: {key} -> {result.get('link')}")
        else:
            created += 1
            print(f"✅ Criado: {key} -> {result.get('link')}")

    save_state(state)

    print(
        f"\nResumo: {created} criados, {updated} atualizados, "
        f"{skipped} sem alteração, {failed} com falha."
    )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
