#!/usr/bin/env python3
"""
Diagnóstico do bloqueio Mod_Security ao criar posts via REST API do WP.
Roda várias requisições de teste (crescendo em tamanho/tipo de conteúdo)
contra /wp-json/wp/v2/posts e reporta o status de cada uma, pra isolar
se o bloqueio é por tamanho do payload, por tipo de conteúdo, ou um
bloqueio genérico contra qualquer POST nesse endpoint.

Cada post de teste é criado como rascunho (status=draft) e IMEDIATAMENTE
apagado (force delete) ao final, pra não sujar o blog.

Variáveis de ambiente obrigatórias: WP_BASE_URL, WP_USER, WP_APP_PASSWORD
"""
import base64
import os

import requests

WP_BASE_URL = os.environ["WP_BASE_URL"].rstrip("/")
WP_USER = os.environ["WP_USER"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]

session = requests.Session()
session.auth = (WP_USER, WP_APP_PASSWORD)


def try_create(label, content, content_type_header="application/json"):
    payload = {
        "title": f"[TESTE DIAGNÓSTICO] {label}",
        "status": "draft",
        "content": content,
    }
    headers = {"Content-Type": content_type_header}
    size_kb = len(str(payload)) / 1024
    try:
        resp = session.post(
            f"{WP_BASE_URL}/wp-json/wp/v2/posts",
            json=payload,
            headers=headers,
            timeout=30,
        )
    except Exception as e:
        print(f"[{label}] (~{size_kb:.1f} KB) -> EXCEÇÃO: {e}")
        return None

    snippet = resp.text[:200].replace("\n", " ")
    print(f"[{label}] (~{size_kb:.1f} KB) -> HTTP {resp.status_code} | {snippet}")

    if resp.status_code in (200, 201):
        try:
            post_id = resp.json()["id"]
            del_resp = session.delete(
                f"{WP_BASE_URL}/wp-json/wp/v2/posts/{post_id}",
                params={"force": "true"},
                timeout=30,
            )
            print(f"    (limpo: post {post_id} deletado, HTTP {del_resp.status_code})")
        except Exception as e:
            print(f"    (⚠️ não consegui limpar o post de teste: {e})")
        return resp.status_code
    return resp.status_code


def main():
    print(f"Testando contra {WP_BASE_URL} como usuário {WP_USER}\n")

    # 1. Payload mínimo — isola bloqueio genérico do endpoint
    try_create("minimo", "teste simples")

    # 2. ~1 KB de texto puro
    try_create("texto-1kb", "A" * 1024)

    # 3. ~10 KB de texto puro
    try_create("texto-10kb", "A" * 1024 * 10)

    # 4. ~50 KB de texto puro
    try_create("texto-50kb", "A" * 1024 * 50)

    # 5. ~1 KB em base64 (bytes aleatórios simulados)
    b64_1kb = base64.b64encode(os.urandom(1024)).decode("ascii")
    try_create("base64-1kb", f'<iframe src="data:text/html;base64,{b64_1kb}"></iframe>')

    # 6. ~20 KB em base64
    b64_20kb = base64.b64encode(os.urandom(1024 * 20)).decode("ascii")
    try_create("base64-20kb", f'<iframe src="data:text/html;base64,{b64_20kb}"></iframe>')

    # 7. HTML com <style> literal (pequeno) — testa se é a tag em si
    try_create("style-tag-pequeno", "<style>body{color:red}</style><p>teste</p>")

    # 8. Edição real (tamanho real de produção), pra confirmar o tamanho exato que falha
    import glob
    files = sorted(glob.glob("edicoes/ed-*.html"))
    if files:
        real_path = files[-1]
        with open(real_path, "r", encoding="utf-8") as f:
            real_html = f.read()
        real_size_kb = len(real_html) / 1024
        print(f"\nTamanho real de {real_path}: {real_size_kb:.1f} KB")
        b64_real = base64.b64encode(real_html.encode("utf-8")).decode("ascii")
        try_create(
            f"edicao-real-base64({real_size_kb:.0f}KB)",
            f'<iframe src="data:text/html;base64,{b64_real}"></iframe>',
        )

    print("\nDiagnóstico concluído.")


if __name__ == "__main__":
    main()
