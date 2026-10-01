"""Arruma o canvas do Maestri pelo plano que a skill canvas-de-agentes escreveu.

Maestro à esquerda, uma área colorida por frente (terminais em grade), estante de notas e navegadores à direita.

O Maestri guarda o canvas em ~/.maestri/workspaces/<id>/workspace.json e regrava esse arquivo
enquanto está aberto. Por isso: FECHE O MAESTRI, rode este script e abra de novo.
Sempre é feita uma cópia de segurança antes de gravar.

Uso (com o Maestri fechado):
  python organizar.py            # aplica o plano
  python organizar.py desfazer   # volta ao canvas de antes da última aplicação
  --plano CAMINHO    plano em JSON (padrão: ~/canvas-de-agentes-plano.json)
  --arquivo CAMINHO  grava em outro workspace.json (para testar numa cópia)
  --forcar           grava mesmo se a versão do arquivo não for a testada

Plano:
  {"linhas": 2, "colunas": 2,
   "maestro": {"nome": "Maestro", "membros": ["<nome do terminal do maestro>", "Governança"]},
   "areas": [{"nome": "Site", "membros": ["Atlas"]}, {"nome": "Clientes", "membros": ["Brisa", "Revisor"]}]}
Membros são os nomes exatos que `maestri list` mostra. "linhas" = em quantas linhas as áreas se dividem;
"colunas" = quantos terminais lado a lado dentro de cada área.
"""
import argparse
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAESTRI = Path.home() / ".maestri"
PLANO_PADRAO = Path.home() / "canvas-de-agentes-plano.json"
SCHEMA_TESTADO = 2

COR_MAESTRO, COR_ESTANTE = "#FFCC00", "#A2845E"
# (cor do terminal, cor de nota que o Maestri aceita) — uma por área, na ordem do plano
PALETA = [("#AF52DE", "purple"), ("#007AFF", "blue"), ("#34C759", "green"),
          ("#FF2D55", "pink"), ("#FF9500", "orange"), ("#8E8E93", "slate")]

ORIGEM = (6000, 7600)          # canto superior esquerdo do arranjo
TAMANHO_MAESTRO = [1100, 680]  # terminal do maestro, maior que os outros (800×500)
LARGURA_TERMINAL = 800
GAP, PAD, CABECALHO, ENTRE_AREAS = 60, 80, 150, 200
LARGURA_ESTANTE = 2000
FONTE_TITULO, FOLGA_TITULO = 56, 24

NS = uuid.UUID("6f1c2a7e-3b1d-4c55-9e0a-2f7d5b8c1a90")  # ids fixos: rodar de novo substitui, não duplica


def kind(n):
    return next(iter(n["content"]))


def dados(n):
    return n["content"][kind(n)]["_0"]


def nome(n):
    c = dados(n)
    return c.get("name") or c.get("fileName") or c.get("text") or ""


def carregar_plano(caminho):
    plano = json.loads(Path(caminho).read_text(encoding="utf-8"))
    maestro = {"nome": plano["maestro"].get("nome", "Maestro"), "cor": COR_MAESTRO, "nota": None,
               "membros": plano["maestro"]["membros"]}
    mesa = []
    linhas = max(1, int(plano.get("linhas", 2)))
    total = len(plano["areas"])
    for i, a in enumerate(plano["areas"]):
        cor, nota = PALETA[i % len(PALETA)]
        mesa.append({"nome": a["nome"], "cor": cor, "nota": nota, "membros": a["membros"],
                     "linha": i * linhas // total})
    estante = {"nome": "Estante", "cor": COR_ESTANTE, "nota": None, "membros": []}
    colunas = max(1, int(plano.get("colunas", 2)))
    return {"maestro": maestro, "mesa": mesa, "estante": estante, "areas": [maestro, *mesa, estante],
            "largura_mesa": colunas * LARGURA_TERMINAL + (colunas - 1) * GAP}


def workspace_ativo():
    estado = json.loads((MAESTRI / "app-state.json").read_text(encoding="utf-8"))
    return MAESTRI / "workspaces" / estado["payload"]["activeWorkspaceId"] / "workspace.json"


def maestri_aberto():
    if sys.platform == "win32":
        saida = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Maestri.exe"], capture_output=True, text=True).stdout
        return "Maestri.exe" in saida
    return subprocess.run(["pgrep", "-x", "Maestri"], capture_output=True).returncode == 0


def id_area(area, parte):
    return str(uuid.uuid5(NS, f"{area}:{parte}")).upper()


def id_rotulo(area):
    return str(uuid.uuid5(NS, f"{area}:rotulo"))


def membros_de_pilha(p):
    return {m for n in p["nodes"] if kind(n) == "noteStack" for m in dados(n)["memberNodeIds"]}


def plano_por_item(nodes, pl):
    por_nome = {}
    for n in nodes:
        por_nome.setdefault(nome(n), []).append(n)
    area_de, faltando = {}, []
    for a in pl["areas"]:
        for m in a["membros"]:
            if m not in por_nome:
                faltando.append(m)
            for n in por_nome.get(m, []):
                area_de[n["id"]] = a
    return area_de, faltando


def empacotar(itens, x0, y0, largura, ordem_nomes=()):
    """Prateleiras: terminais, depois fichários e notas, por fim navegadores; quebra de linha pela largura."""
    ordem = {"terminal": 0, "noteStack": 1, "stickyNote": 1, "portal": 2}
    pos = {m: i for i, m in enumerate(ordem_nomes)}
    itens = sorted(itens, key=lambda n: (ordem.get(kind(n), 3), pos.get(nome(n), 999), nome(n)))
    largura = max([largura] + [n["frame"][1][0] for n in itens])
    x, y, alt_linha = x0, y0, 0
    for n in itens:
        w, h = n["frame"][1]
        if x > x0 and x + w > x0 + largura:
            x, y, alt_linha = x0, y + alt_linha + GAP, 0
        n["frame"][0] = [x, y]
        x += w + GAP
        alt_linha = max(alt_linha, h)


def caixa(itens):
    return (min(n["frame"][0][0] for n in itens), min(n["frame"][0][1] for n in itens),
            max(n["frame"][0][0] + n["frame"][1][0] for n in itens),
            max(n["frame"][0][1] + n["frame"][1][1] for n in itens))


def area_em(itens, x, y, largura, ordem_nomes=()):
    empacotar(itens, x + PAD, y + PAD + CABECALHO, largura, ordem_nomes)
    x0, y0, x1, y1 = caixa(itens)
    return x1 - x0 + 2 * PAD, y1 - y0 + 2 * PAD + CABECALHO


def aplicar_layout(p, pl):
    """Move os itens e devolve (grupos por área, nomes do plano que não existem no canvas)."""
    area_de, faltando = plano_por_item(p["nodes"], pl)
    dentro = membros_de_pilha(p)
    itens = [n for n in p["nodes"] if n["id"] in area_de and n["id"] not in dentro]
    maestro = [n for n in itens if area_de[n["id"]] is pl["maestro"]]
    for n in maestro:
        if kind(n) == "terminal":
            n["frame"][1] = list(TAMANHO_MAESTRO)

    mx = ORIGEM[0] + (TAMANHO_MAESTRO[0] + 2 * PAD + ENTRE_AREAS if maestro else 0)
    y, fim_mesa = ORIGEM[1], mx
    for linha in sorted({a["linha"] for a in pl["mesa"]}):
        x, alt = mx, 0
        for a in [a for a in pl["mesa"] if a["linha"] == linha]:
            terms = [n for n in itens if area_de[n["id"]] is a and kind(n) == "terminal"]
            if terms:
                w, h = area_em(terms, x, y, pl["largura_mesa"], a["membros"])
                x += w + ENTRE_AREAS
                alt = max(alt, h)
        fim_mesa = max(fim_mesa, x)
        y += alt + ENTRE_AREAS
    altura_mesa = max(0, y - ENTRE_AREAS - ORIGEM[1])

    if maestro:
        _, h_maestro = area_em(maestro, ORIGEM[0], ORIGEM[1], TAMANHO_MAESTRO[0])
        desce = max(0, (altura_mesa - h_maestro) / 2)  # centraliza o maestro na altura da mesa
        for n in maestro:
            n["frame"][0][1] += desce

    leitura = [n for n in itens if kind(n) != "terminal" and area_de[n["id"]] is not pl["maestro"]]
    if leitura:
        area_em(leitura, fim_mesa, ORIGEM[1], LARGURA_ESTANTE, [m for a in pl["mesa"] for m in a["membros"]])

    por_id = {n["id"]: n for n in p["nodes"]}
    grupos = {a["nome"]: [] for a in pl["areas"]}
    for n in itens:
        a = area_de[n["id"]]
        c = dados(n)
        if kind(n) == "terminal":
            c["color"] = a["cor"]
        elif kind(n) == "stickyNote" and a["nota"]:
            c["color"] = a["nota"]
        elif kind(n) == "noteStack":
            for m in c["memberNodeIds"]:
                if m in por_id:
                    por_id[m]["frame"][0] = list(n["frame"][0])  # notas acompanham o fichário
                    if a["nota"]:
                        dados(por_id[m])["color"] = a["nota"]
        destino = a if kind(n) == "terminal" or a is pl["maestro"] else pl["estante"]
        grupos[destino["nome"]].append(n)
    return grupos, faltando


def refazer_cordas(p):
    """Cada corda guarda 21 pontos; depois de mover, refaz em linha reta entre as bordas mais próximas."""
    por_id = {n["id"]: n for n in p["nodes"]}

    def ancora(a, b):
        (ax, ay), (aw, ah) = a["frame"]
        (bx, by), (bw, bh) = b["frame"]
        dx, dy = (bx + bw / 2) - (ax + aw / 2), (by + bh / 2) - (ay + ah / 2)
        if abs(dx) * ah >= abs(dy) * aw:
            return (ax + aw if dx > 0 else ax, ay + ah / 2)
        return (ax + aw / 2, ay + ah if dy > 0 else ay)

    for lista, ka, kb in [("connections", "terminalIdA", "terminalIdB"),
                          ("noteConnections", "noteNodeId", "terminalId"),
                          ("portalConnections", "portalNodeId", "terminalId")]:
        for c in p.get(lista, []):
            a, b = por_id.get(c[ka]), por_id.get(c[kb])
            if a and b:
                (x0, y0), (x1, y1) = ancora(a, b), ancora(b, a)
                c["ropePoints"] = [[x0 + (x1 - x0) * i / 20, y0 + (y1 - y0) * i / 20] for i in range(21)]


def desenhar_areas(p, grupos, pl):
    """Fundo e etiqueta são desenhos; o nome da área é um item de texto. Tudo abaixo dos itens do canvas."""
    meus = {id_area(a["nome"], parte) for a in pl["areas"] for parte in ("fundo", "titulo")}
    rotulos = {id_rotulo(a["nome"]) for a in pl["areas"]}
    p["drawings"] = [d for d in p.get("drawings", []) if d.get("id") not in meus]
    p["nodes"] = [n for n in p["nodes"] if n["id"] not in rotulos]
    z = min([d.get("zIndex", 0) for d in p["drawings"]] + [n.get("zIndex", 0) for n in p["nodes"]] + [1]) \
        - 3 * len(pl["areas"]) - 1
    agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for a in pl["areas"]:
        itens = grupos[a["nome"]]
        if not itens:
            continue
        x0, y0, x1, y1 = caixa(itens)
        x0, y0, x1, y1 = x0 - PAD, y0 - PAD - CABECALHO, x1 + PAD, y1 + PAD
        w, h = x1 - x0, y1 - y0
        base = {"rotation": 0, "isLocked": True, "color": a["cor"], "tool": "rectangle", "fillStyle": "tint",
                "opacity": 1, "textFontSize": 20,
                "strokePattern": "dashed" if a is pl["estante"] else "solid"}
        p["drawings"].append({**base, "id": id_area(a["nome"], "fundo"), "points": [[0, 0], [w, h]],
                              "origin": [x0, y0], "size": [w, h], "originalSize": [w, h],
                              "lineWidth": 6 if a is pl["maestro"] else 3, "zIndex": z})
        tw, th = round(len(a["nome"]) * FONTE_TITULO * 0.62) + 20, round(FONTE_TITULO * 1.7)
        larg, alt = tw + 2 * FOLGA_TITULO, th + FOLGA_TITULO
        ex, ey = x0 + PAD, y0 + (CABECALHO + PAD - alt) / 2
        p["drawings"].append({**base, "id": id_area(a["nome"], "titulo"), "points": [[0, 0], [larg, alt]],
                              "origin": [ex, ey], "size": [larg, alt], "originalSize": [larg, alt],
                              "lineWidth": 2, "zIndex": z + 1})
        p["nodes"].append({"id": id_rotulo(a["nome"]), "createdAt": agora, "lastModifiedAt": agora,
                           "isLocked": True, "isRedacted": False, "zIndex": z + 2,
                           "frame": [[ex + FOLGA_TITULO, ey + FOLGA_TITULO / 2], [tw, th]],
                           "content": {"textBlock": {"_0": {"text": a["nome"], "fontSize": FONTE_TITULO,
                                                            "isMonospaced": False}}}})
        z += 3


def organizar(doc, pl):
    """Aplica o plano ao documento (em memória) e devolve os avisos."""
    p = doc["payload"]
    grupos, faltando = aplicar_layout(p, pl)
    refazer_cordas(p)
    desenhar_areas(p, grupos, pl)
    avisos = [f"'{m}' está no plano mas não existe no canvas (ignorado)" for m in faltando]
    colocados = {n["id"] for g in grupos.values() for n in g} | membros_de_pilha(p) \
        | {id_rotulo(a["nome"]) for a in pl["areas"]}
    avisos += [f"'{nome(n)}' não está no plano (ficou onde estava)" for n in p["nodes"]
               if n["id"] not in colocados and kind(n) != "textBlock"]
    return avisos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("modo", nargs="?", default="aplicar", choices=["aplicar", "desfazer"])
    ap.add_argument("--plano", type=Path, default=PLANO_PADRAO)
    ap.add_argument("--arquivo", type=Path)
    ap.add_argument("--forcar", action="store_true")
    args = ap.parse_args()

    if not args.arquivo and not MAESTRI.exists():
        sys.exit(f"Não achei a pasta do Maestri em {MAESTRI}. Nada foi alterado.")
    arquivo = args.arquivo or workspace_ativo()
    if not args.arquivo and maestri_aberto():
        sys.exit("O Maestri está aberto. Feche o aplicativo e rode de novo. Nada foi alterado.")
    backups = arquivo.parent if args.arquivo else MAESTRI / "backups"
    marca = arquivo.parent.name

    if args.modo == "desfazer":
        anteriores = sorted(backups.glob(f"antes-canvas-{marca}-*.json"))
        if not anteriores:
            sys.exit("Não há cópia de segurança deste workspace para desfazer.")
        shutil.copy2(anteriores[-1], arquivo)
        print(f"desfeito: o canvas voltou ao estado de {anteriores[-1].name}. Abra o Maestri.")
        return

    doc = json.loads(arquivo.read_text(encoding="utf-8"))
    if doc.get("schemaVersion") != SCHEMA_TESTADO and not args.forcar:
        sys.exit(f"Este Maestri grava o canvas na versão {doc.get('schemaVersion')}; o script foi testado na "
                 f"{SCHEMA_TESTADO}. Nada foi alterado. Arraste as caixas à mão ou use --forcar por sua conta.")
    if not args.plano.exists():
        sys.exit(f"Plano não encontrado em {args.plano}. Rode /canvas-de-agentes no Maestri para criar.")
    for aviso in organizar(doc, carregar_plano(args.plano)):
        print("aviso:", aviso)

    backup = backups / f"antes-canvas-{marca}-{datetime.now():%Y%m%d-%H%M%S}.json"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(arquivo, backup)
    tmp = arquivo.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(arquivo)
    print(f"pronto: canvas arrumado. Abra o Maestri.\ncópia de segurança: {backup}\n"
          f"Para voltar atrás: feche o Maestri e rode  python {Path(__file__).name} desfazer")


if __name__ == "__main__":
    main()
