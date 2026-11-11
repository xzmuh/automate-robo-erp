"""Robô de exemplo do Next Automate.

1. Abre o erp.html no Edge instalado (Playwright, perfil fixo numa pasta).
2. Cadastra as linhas do dados.txt ("Nome;CPF;Valor"), com uma pausa curta entre elas.
3. Abre a Calculadora do Windows (pywinauto), digita a soma de todos os valores
   e confere o resultado com a conta feita aqui.
"""

import os
import re
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright
from pywinauto import Desktop

PASTA = Path(__file__).resolve().parent
ERP = PASTA / "erp.html"
DADOS = PASTA / "dados.txt"
# Perfil fixo do Edge: fica fora da pasta do robô, para sobreviver às versões novas.
PERFIL = Path(os.environ.get("PERFIL_EDGE") or
              Path(os.environ.get("LOCALAPPDATA", PASTA)) / "NextAutomate" / "robo-erp" / "perfil-edge")
PAUSA = float(os.environ.get("PAUSA", "0.5"))


def log(msg):
    print(msg, flush=True)


def ler_dados():
    linhas = []
    for n, bruta in enumerate(DADOS.read_text(encoding="utf-8").splitlines(), 1):
        if not bruta.strip():
            continue
        partes = [p.strip() for p in bruta.split(";")]
        if len(partes) != 3:
            raise SystemExit(f"dados.txt linha {n}: esperado Nome;CPF;Valor, veio {bruta!r}")
        nome, cpf, valor = partes
        linhas.append((nome, cpf, valor, Decimal(valor.replace(".", "").replace(",", "."))))
    return linhas


def brl(v):
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "_").replace(".", ",").replace("_", ".")


def cadastrar(linhas):
    PERFIL.mkdir(parents=True, exist_ok=True)
    log(f"Abrindo o Edge (perfil em {PERFIL})")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PERFIL), channel="msedge", headless=False, no_viewport=True,
            args=["--start-maximized"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(ERP.as_uri())
            log(f"ERP aberto: {page.title()}")
            page.click("#limpar")
            log("Lista de cadastros anterior limpa")

            for i, (nome, cpf, valor, _) in enumerate(linhas, 1):
                page.fill("#nome", nome)
                page.fill("#cpf", cpf)
                page.fill("#valor", valor)
                page.click("#salvar")
                page.wait_for_function("n => document.querySelectorAll('#lista tr').length === n", arg=i)
                log(f"[{i:02d}/{len(linhas)}] cadastrado: {nome} | {cpf} | R$ {valor}")
                time.sleep(PAUSA)

            qtd = page.inner_text("#qtd")
            total_tela = page.inner_text("#total").replace("\xa0", " ")
            log(f"ERP mostra {qtd} clientes salvos, total {total_tela}")
            if int(qtd) != len(linhas):
                raise SystemExit(f"esperava {len(linhas)} cadastros na lista, o ERP mostra {qtd}")

            artefatos = os.environ.get("ARTIFACTS_DIR")
            if artefatos:
                destino = Path(artefatos) / "erp.png"
                page.screenshot(path=str(destino), full_page=True)
                log(f"Foto do ERP salva em {destino.name}")
            time.sleep(2)
        finally:
            ctx.close()
            log("Edge fechado")


def teclas_do_valor(valor):
    # {VK_DECIMAL} é a vírgula/ponto do teclado numérico: a Calculadora usa o
    # separador decimal do Windows, seja ele qual for.
    return "".join("{VK_DECIMAL}" if c in ",." else c for c in valor.replace(".", "") if c in "0123456789,")


def ler_visor(janela, portugues):
    texto = janela.child_window(auto_id="CalculatorResults", control_type="Text").window_text()
    achado = re.findall(r"-?[\d.,]+", texto)
    if not achado:
        raise SystemExit(f"não consegui ler o visor da Calculadora: {texto!r}")
    n = achado[-1]
    if "," in n and "." in n:
        decimal = "," if n.rfind(",") > n.rfind(".") else "."
    else:
        decimal = "," if portugues else "."
    milhar = "." if decimal == "," else ","
    return texto, Decimal(n.replace(milhar, "").replace(decimal, "."))


def somar_na_calculadora(linhas):
    log("Abrindo a Calculadora do Windows")
    subprocess.Popen(["calc.exe"])
    janela = Desktop(backend="uia").window(title_re=r"^(Calculadora|Calculator)$", control_type="Window")
    janela.wait("visible", timeout=20)
    portugues = janela.window_text() == "Calculadora"
    janela.set_focus()
    janela.type_keys("%1", pause=0.05)   # Alt+1: modo Padrão
    janela.type_keys("{ESC}", pause=0.05)  # zera
    log("Calculadora pronta (modo Padrão)")

    for i, (_, _, valor, _) in enumerate(linhas, 1):
        janela.type_keys(teclas_do_valor(valor), pause=0.04)
        if i < len(linhas):
            janela.type_keys("{+}", pause=0.04)
        log(f"[{i:02d}/{len(linhas)}] digitado: {valor}" + (" +" if i < len(linhas) else ""))
        time.sleep(0.15)
    janela.type_keys("{ENTER}")
    time.sleep(0.5)

    texto, resultado = ler_visor(janela, portugues)
    log(f"Visor da Calculadora: {texto}")
    time.sleep(3)
    janela.close()
    log("Calculadora fechada")
    return resultado


def main():
    linhas = ler_dados()
    esperado = sum(v for *_, v in linhas)
    log(f"{len(linhas)} cadastros lidos do dados.txt")

    cadastrar(linhas)
    resultado = somar_na_calculadora(linhas)

    log(f"Total pela Calculadora: {brl(resultado)}")
    log(f"Total conferido pelo robô: {brl(esperado)}")
    if resultado != esperado:
        log("ERRO: a soma da Calculadora não bate com a dos dados")
        sys.exit(1)
    log(f"TOTAL: {brl(esperado)}")


if __name__ == "__main__":
    main()
