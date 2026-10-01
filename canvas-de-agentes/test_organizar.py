"""python test_organizar.py — confere o arranjo (maestro à esquerda, áreas em grade, estante) sem tocar no Maestri."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import organizar as og


def term(nid, nome):
    return {"id": nid, "frame": [[0, 0], [800, 500]], "zIndex": 1,
            "content": {"terminal": {"_0": {"name": nome, "color": "#000000"}}}}


def portal(nid, nome):
    return {"id": nid, "frame": [[0, 0], [1280, 956]], "zIndex": 1, "content": {"portal": {"_0": {"name": nome}}}}


def doc():
    return {"schemaVersion": 2, "type": "workspace", "payload": {
        "nodes": [term("k", "Maestro"), term("a", "Atlas"), term("b", "Brisa"), term("c", "Cedro"),
                  portal("t", "Painel"), term("x", "Fora do plano")],
        "connections": [{"terminalIdA": "k", "terminalIdB": "a", "ropePoints": []}],
        "noteConnections": [], "portalConnections": [], "drawings": []}}


plano = {"linhas": 2, "colunas": 2, "maestro": {"membros": ["Maestro"]},
         "areas": [{"nome": "Site", "membros": ["Atlas", "Painel"]}, {"nome": "Fantasma", "membros": ["Não existe"]},
                   {"nome": "Clientes", "membros": ["Brisa", "Cedro"]}]}  # 3 áreas em 2 linhas: 2 em cima, 1 embaixo

with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "plano.json").write_text(json.dumps(plano), encoding="utf-8")
    pl = og.carregar_plano(d / "plano.json")

    w = doc()
    avisos = og.organizar(w, pl)
    og.organizar(w, pl)  # rodar de novo não duplica áreas
    p = w["payload"]
    por = {n["id"]: n for n in p["nodes"]}
    assert any("Não existe" in a for a in avisos) and any("Fora do plano" in a for a in avisos), avisos
    assert por["x"]["frame"][0] == [0, 0], "item fora do plano não se move"
    assert por["k"]["frame"][1] == og.TAMANHO_MAESTRO, "maestro maior"
    assert por["k"]["frame"][0][0] < min(por[i]["frame"][0][0] for i in "abct"), "maestro à esquerda de tudo"
    assert por["t"]["frame"][0][0] > max(por[i]["frame"][0][0] for i in "abc"), "navegador na estante, à direita"
    assert por["b"]["frame"][0][1] == por["c"]["frame"][0][1], "2 colunas: Brisa e Cedro lado a lado"
    assert por["b"]["frame"][0][1] > por["a"]["frame"][0][1], "2 linhas: Clientes abaixo de Site"
    cores = {i: og.dados(por[i])["color"] for i in "kabc"}
    assert cores == {"k": "#FFCC00", "a": "#AF52DE", "b": "#34C759", "c": "#34C759"}, cores
    textos = sorted(og.dados(n)["text"] for n in p["nodes"] if og.kind(n) == "textBlock")
    assert textos == ["Clientes", "Estante", "Maestro", "Site"], textos  # área sem itens não é desenhada
    assert len(p["drawings"]) == 8 and len(p["connections"][0]["ropePoints"]) == 21

    # 1 linha e 1 coluna: áreas lado a lado, terminais empilhados
    w2 = doc()
    (d / "p2.json").write_text(json.dumps({**plano, "linhas": 1, "colunas": 1}), encoding="utf-8")
    og.organizar(w2, og.carregar_plano(d / "p2.json"))
    por2 = {n["id"]: n for n in w2["payload"]["nodes"]}
    assert por2["b"]["frame"][0][1] == por2["a"]["frame"][0][1], "1 linha: Clientes ao lado de Site"
    assert por2["c"]["frame"][0][1] > por2["b"]["frame"][0][1], "1 coluna: Cedro abaixo de Brisa"

    # pela linha de comando numa cópia: grava, faz backup, desfaz; versão desconhecida é recusada
    arq = d / "ws" / "workspace.json"
    arq.parent.mkdir()
    original = json.dumps(doc())
    arq.write_text(original, encoding="utf-8")
    cmd = [sys.executable, og.__file__, "--arquivo", str(arq), "--plano", str(d / "plano.json")]
    assert subprocess.run(cmd, capture_output=True).returncode == 0
    assert json.loads(arq.read_text(encoding="utf-8"))["payload"]["drawings"], "gravou"
    assert subprocess.run([*cmd, "desfazer"], capture_output=True).returncode == 0
    assert arq.read_text(encoding="utf-8") == original, "desfazer devolve o arquivo idêntico"
    arq.write_text(json.dumps({**doc(), "schemaVersion": 3}), encoding="utf-8")
    assert subprocess.run(cmd, capture_output=True).returncode != 0, "versão desconhecida: recusa"
    assert json.loads(arq.read_text(encoding="utf-8"))["schemaVersion"] == 3, "e não altera"
print("ok")
