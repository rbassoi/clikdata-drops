#!/usr/bin/env python3
"""
Publica notícias diárias (noticias/AAAA-MM-DD.json) como posts individuais
no WordPress (drops.clikdata.com.br), na categoria "Notícias".

Totalmente separado do fluxo da newsletter (edicoes/ + migrate_wordpress.py
+ wp-migration-state.json) — usa pasta, script, manifesto e workflow
próprios, pra nunca interferir na geração/disparo da newsletter.

Usa a mesma rota REST custom /wp-json/clikdata/v1/posts do plugin
clikdata-drops-publish-api (contorna o Mod_Security do endpoint padrão).

Formato esperado do JSON (lista de notícias do dia):
[
  {
    "title": "Título da notícia",
    "summary": "Resumo em 2-3 frases.",
    "source_name": "TechCrunch",
    "source_url": "https://...",
    "tag": "IA"            # IA, Tecnologia ou Transformação Digital
  },
  ...
]

Idempotente: manifesto próprio (wp-news-state.json) mapeando
"<arquivo>#<índice>" -> post_id/post_url/content_hash. Notícia só é
recriada/atualizada se o conteúdo mudou.

Uso:
  python3 scripts/publish_daily_news.py                          # processa todos os arquivos em noticias/
  python3 scripts/publish_daily_news.py noticias/2026-09-21.json  # processa só um dia
  python3 scripts/publish_daily_news.py --force                  # reprocessa tudo, ignorando o cache de hash

Variáveis de ambiente obrigatórias (iguais ao migrate_wordpress.py):
  WP_BASE_URL       ex: https://drops.clikdata.com.br
  WP_USER           usuário WordPress real (ex: rbassoi)
  WP_APP_PASSWORD   Application Password gerado no WP (com espaços, ok)
"""
import glob
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

import requests

STATE_FILE = "wp-news-state.json"
NEWS_GLOB = "noticias/*.json"
FILENAME_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.json$")

POST_TEMPLATE = """<!-- wp:paragraph -->
<p>{summary}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph -->
<p><strong>Fonte:</strong> <a href="{source_url}" target="_blank" rel="noopener noreferrer">{source_name}</a></p>
<!-- /wp:paragraph -->"""


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def wp_session():
    user = os.environ["WP_USER"]
    app_password = os.environ["WP_APP_PASSWORD"]
    base_url = os.environ["WP_BASE_URL"].rstrip("/")
    s = requests.Session()
    s.auth = (user, app_password)
    s.headers.update({
        "Content-Type": "application/json",
        # Mesmo motivo do migrate_wordpress.py: evita bloqueio de
        # Mod_Security baseado no User-Agent padrão do requests.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ),
    })
    return s, base_url


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def build_post_payload(data_iso, idx, item):
    title = item["title"]
    slug = f"noticia-{data_iso}-{idx + 1:02d}-{slugify(title)}"
    content = POST_TEMPLATE.format(
        summary=html.escape(item.get("summary", "")),
        source_url=html.escape(item["source_url"], quote=True),
        source_name=html.escape(item.get("source_name", "Fonte")),
    )
    excerpt = item.get("summary", "")[:200]
    return {
        "title": title,
        "slug": slug,
        "status": "publish",
        "date": f"{data_iso}T08:00:00",
        "content": content,
        "excerpt": excerpt,
        "category": "Notícias",
    }


def upsert_post(session, base_url, payload, existing_post_id):
    url = f"{base_url}/wp-json/clikdata/v1/posts"
    body = dict(payload)
    if existing_post_id:
        body["id"] = existing_post_id
    resp = session.post(url, json=body, timeout=60)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"WP API {resp.status_code} em {url}: {resp.text[:500]}")
    return resp.json()


def main():
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    force = "--force" in args
    args = [a for a in args if a != "--force"]
    files = args if args else sorted(glob.glob(NEWS_GLOB))
    if not files:
        print("Nenhum arquivo de notícias encontrado.")
        return

    state = load_state()
    session, base_url = wp_session()

    created, updated, skipped, failed = 0, 0, 0, 0

    for path in files:
        m = FILENAME_RE.search(os.path.basename(path))
        if not m:
            print(f"⚠️  Ignorando (nome fora do padrão AAAA-MM-DD.json): {path}")
            continue
        data_iso = m.group(1)

        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)

        for idx, item in enumerate(items):
            key = f"{os.path.basename(path)}#{idx}"
            content_hash = hashlib.sha256(
                json.dumps(item, sort_keys=True, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            entry = state.get(key)

            if not force and entry and entry.get("content_hash") == content_hash:
                skipped += 1
                continue

            payload = build_post_payload(data_iso, idx, item)

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
