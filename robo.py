"""Robô de exemplo do Next Automate: cadastro de fornecedores.

1. Mostra o dados.txt no Bloco de Notas e conta 3 segundos.
2. Abre o erp.html no Edge (Playwright, perfil fixo), vai em Fornecedores e,
   para cada linha, clica em Novo fornecedor, preenche e salva.
3. Com o ERP ainda aberto, abre a Calculadora por cima, soma os valores
   e confere com a conta feita aqui.
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
    for n, bruta in enumerate(DADOS.read_text(encoding="utf-8-sig").splitlines(), 1):
        if n == 1 or not bruta.strip():
            continue
        partes = [p.strip() for p in bruta.split(";")]
        if len(partes) != 5:
            raise SystemExit(f"dados.txt linha {n}: esperado Razão social;CNPJ;E-mail;Categoria;Valor, veio {bruta!r}")
        razao, cnpj, email, categoria, valor = partes
        linhas.append({
            "razao": razao, "cnpj": cnpj, "email": email, "categoria": categoria, "valor": valor,
            "numero": Decimal(valor.replace(".", "").replace(",", ".")),
        })
    return linhas


def brl(v):
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "_").replace(".", ",").replace("_", ".")


def mostrar_no_bloco_de_notas():
    log("Abrindo os dados no Bloco de Notas")
    subprocess.Popen(["notepad.exe", str(DADOS)])
    janela = None
    try:
        janela = Desktop(backend="uia").window(title_re=r".*dados.*", control_type="Window")
        janela.wait("visible", timeout=15)
        janela.set_focus()
    except Exception as erro:
        log(f"Bloco de Notas aberto, sem pegar o foco ({erro})")
        janela = None
    for falta in (3, 2, 1):
        log(f"Começando em {falta}...")
        time.sleep(1)
    if janela is not None:
        try:
            janela.close()
        except Exception:
            pass


def cadastrar_e_somar(linhas):
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
            time.sleep(PAUSA)
            page.click("#menu-fornecedores")
            log("Menu Cadastros > Fornecedores")
            page.click("#limpar")
            log("Lista de fornecedores anterior limpa")
            time.sleep(PAUSA)

            for i, item in enumerate(linhas, 1):
                page.click("#novo-fornecedor")
                page.fill("#razao", item["razao"])
                page.fill("#cnpj", item["cnpj"])
                page.fill("#email", item["email"])
                page.select_option("#categoria", label=item["categoria"])
                page.fill("#valor", item["valor"])
                time.sleep(PAUSA / 2)
                page.click("#salvar")
                page.wait_for_function("n => document.querySelectorAll('#lista tr').length === n", arg=i)
                log(f"[{i:02d}/{len(linhas)}] fornecedor salvo: {item['razao']} | {item['cnpj']} | R$ {item['valor']}")
                time.sleep(PAUSA)

            qtd = page.inner_text("#qtd")
            total_tela = page.inner_text("#total").replace("\xa0", " ")
            log(f"ERP mostra {qtd} fornecedores, total {total_tela}")
            if int(qtd) != len(linhas):
                raise SystemExit(f"esperava {len(linhas)} fornecedores na lista, o ERP mostra {qtd}")

            artefatos = os.environ.get("ARTIFACTS_DIR")
            if artefatos:
                destino = Path(artefatos) / "erp.png"
                page.screenshot(path=str(destino), full_page=True)
                log(f"Foto do ERP salva em {destino.name}")

            return somar_na_calculadora(linhas)
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
    log("Abrindo a Calculadora por cima do ERP")
    subprocess.Popen(["calc.exe"])
    janela = Desktop(backend="uia").window(title_re=r"^(Calculadora|Calculator)$", control_type="Window")
    janela.wait("visible", timeout=20)
    portugues = janela.window_text() == "Calculadora"
    janela.set_focus()
    janela.type_keys("%1", pause=0.05)   # Alt+1: modo Padrão
    janela.type_keys("{ESC}", pause=0.05)  # zera
    log("Calculadora pronta (modo Padrão)")

    for i, item in enumerate(linhas, 1):
        janela.type_keys(teclas_do_valor(item["valor"]), pause=0.04)
        if i < len(linhas):
            janela.type_keys("{+}", pause=0.04)
        log(f"[{i:02d}/{len(linhas)}] digitado: {item['valor']}" + (" +" if i < len(linhas) else ""))
        time.sleep(0.15)
    janela.type_keys("{ENTER}")
    time.sleep(0.5)

    texto, resultado = ler_visor(janela, portugues)
    log(f"Visor da Calculadora: {texto}")
    time.sleep(4)
    janela.close()
    log("Calculadora fechada")
    return resultado


def main():
    linhas = ler_dados()
    esperado = sum(item["numero"] for item in linhas)
    log(f"{len(linhas)} fornecedores lidos do dados.txt")

    mostrar_no_bloco_de_notas()
    resultado = cadastrar_e_somar(linhas)

    log(f"Total pela Calculadora: {brl(resultado)}")
    log(f"Total conferido pelo robô: {brl(esperado)}")
    if resultado != esperado:
        log("ERRO: a soma da Calculadora não bate com a dos dados")
        sys.exit(1)
    log(f"TOTAL: {brl(esperado)}")


if __name__ == "__main__":
    main()
