"""Robô de exemplo do Next Automate: rotina de contas a pagar num ERP.

1. Mostra o dados.txt no Bloco de Notas e conta 3 segundos.
2. Abre o erp.html no Edge (Playwright, perfil fixo) e entra com usuário e senha.
3. Fornecedores: cadastra cada linha (Novo fornecedor > preenche > Salvar).
4. Contas a pagar: lança uma conta por fornecedor, com o vencimento do dados.txt.
5. Dá baixa nas contas que vencem em até 7 dias.
6. Relatórios: exporta as contas em aberto e abre o arquivo no Bloco de Notas.
7. Abre a Calculadora por cima do ERP, soma o que ficou em aberto e confere
   com o total do ERP e com a conta feita aqui.
"""

import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
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
RELATORIO = Path(os.environ.get("USERPROFILE", PASTA)) / "Documents" / "contas-em-aberto.csv"
PAUSA = float(os.environ.get("PAUSA", "0.4"))
DIAS_PARA_PAGAR = 7


def log(msg):
    print(msg, flush=True)


def etapa(titulo):
    log("")
    log(f"=== {titulo} ===")


def ler_dados():
    linhas = []
    for n, bruta in enumerate(DADOS.read_text(encoding="utf-8-sig").splitlines(), 1):
        if n == 1 or not bruta.strip():
            continue
        partes = [p.strip() for p in bruta.split(";")]
        if len(partes) != 6:
            raise SystemExit(f"dados.txt linha {n}: esperado Razão social;CNPJ;E-mail;Categoria;Valor;Vence em (dias), veio {bruta!r}")
        razao, cnpj, email, categoria, valor, dias = partes
        linhas.append({
            "razao": razao, "cnpj": cnpj, "email": email, "categoria": categoria, "valor": valor,
            "numero": Decimal(valor.replace(".", "").replace(",", ".")), "dias": int(dias),
        })
    return linhas


def brl(v):
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "_").replace(".", ",").replace("_", ".")


def foto(page, nome):
    artefatos = os.environ.get("ARTIFACTS_DIR")
    if artefatos:
        page.screenshot(path=str(Path(artefatos) / f"{nome}.png"), full_page=True)
        log(f"Foto: {nome}.png")


def abrir_no_bloco_de_notas(arquivo, segundos, contagem=False):
    subprocess.Popen(["notepad.exe", str(arquivo)])
    janela = None
    try:
        janela = Desktop(backend="uia").window(title_re=rf".*{re.escape(arquivo.stem)}.*", control_type="Window")
        janela.wait("visible", timeout=15)
        janela.set_focus()
    except Exception as erro:
        log(f"Bloco de Notas aberto, sem pegar o foco ({erro})")
        janela = None
    for falta in range(segundos, 0, -1):
        if contagem:
            log(f"Começando em {falta}...")
        time.sleep(1)
    if janela is not None:
        try:
            janela.close()
        except Exception:
            pass


def entrar(page):
    etapa("Login")
    page.goto(ERP.as_uri())
    page.fill("#usuario", "robo")
    page.fill("#senha", "next123")
    time.sleep(PAUSA)
    page.click("#entrar")
    page.wait_for_selector("#app:not([hidden])")
    log("Entrou no ERP como robo")


def cadastrar_fornecedores(page, linhas):
    etapa("Fornecedores")
    page.click("#menu-fornecedores")
    page.click("#limpar")
    log("Dados da execução anterior apagados")
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
        log(f"[{i:02d}/{len(linhas)}] fornecedor: {item['razao']} | {item['cnpj']}")
        time.sleep(PAUSA / 2)
    foto(page, "1-fornecedores")


def lancar_contas(page, linhas):
    etapa("Contas a pagar")
    page.click("#menu-contas")
    for i, item in enumerate(linhas, 1):
        vencimento = date.today() + timedelta(days=item["dias"])
        page.click("#nova-conta")
        page.select_option("#conta-fornecedor", label=item["razao"])
        page.fill("#conta-descricao", f"Contrato de {item['categoria'].lower()}")
        page.fill("#conta-vencimento", vencimento.isoformat())
        page.fill("#conta-valor", item["valor"])
        time.sleep(PAUSA / 2)
        page.click("#salvar-conta")
        page.wait_for_function("n => document.querySelectorAll('#lista-contas tr').length === n", arg=i)
        log(f"[{i:02d}/{len(linhas)}] conta: {item['razao']} | vence {vencimento:%d/%m} | R$ {item['valor']}")
        time.sleep(PAUSA / 2)
    foto(page, "2-contas-lancadas")


def dar_baixa(page):
    etapa(f"Pagamentos (vencendo em até {DIAS_PARA_PAGAR} dias)")
    page.fill("#filtro-dias", str(DIAS_PARA_PAGAR))
    page.click("#filtrar")
    time.sleep(PAUSA)
    pagas = 0
    while True:
        botoes = page.locator("#lista-contas button.baixar:visible")
        if botoes.count() == 0:
            break
        fornecedor = botoes.first.locator("xpath=ancestor::tr/td[1]").inner_text()
        botoes.first.click()
        pagas += 1
        log(f"Baixa: {fornecedor}")
        time.sleep(PAUSA)
    page.click("#limpar-filtro")
    log(f"{pagas} contas pagas")
    foto(page, "3-pagamentos")
    return pagas


def exportar_relatorio(page):
    etapa("Relatório")
    page.click("#menu-relatorio")
    time.sleep(PAUSA)
    with page.expect_download() as baixando:
        page.click("#exportar")
    RELATORIO.parent.mkdir(parents=True, exist_ok=True)
    baixando.value.save_as(str(RELATORIO))
    log(f"Relatório salvo em {RELATORIO}")
    foto(page, "4-relatorio")
    abrir_no_bloco_de_notas(RELATORIO, 4)
    valores = []
    for linha in RELATORIO.read_text(encoding="utf-8-sig").splitlines()[1:]:
        if linha.strip():
            valores.append(linha.split(";")[-1])
    log(f"{len(valores)} contas em aberto no relatório")
    return valores


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


def somar_na_calculadora(valores):
    etapa("Calculadora")
    subprocess.Popen(["calc.exe"])
    janela = Desktop(backend="uia").window(title_re=r"^(Calculadora|Calculator)$", control_type="Window")
    janela.wait("visible", timeout=20)
    portugues = janela.window_text() == "Calculadora"
    janela.set_focus()
    janela.type_keys("%1", pause=0.05)   # Alt+1: modo Padrão
    janela.type_keys("{ESC}", pause=0.05)  # zera
    log("Calculadora aberta por cima do ERP")

    for i, valor in enumerate(valores, 1):
        janela.type_keys(teclas_do_valor(valor), pause=0.04)
        if i < len(valores):
            janela.type_keys("{+}", pause=0.04)
        log(f"[{i:02d}/{len(valores)}] {valor}" + (" +" if i < len(valores) else ""))
        time.sleep(0.15)
    janela.type_keys("{ENTER}")
    time.sleep(0.5)

    texto, resultado = ler_visor(janela, portugues)
    log(f"Visor: {texto}")
    time.sleep(4)
    janela.close()
    return resultado


def main():
    linhas = ler_dados()
    log(f"{len(linhas)} fornecedores lidos do dados.txt")
    abertas_esperadas = [item for item in linhas if item["dias"] > DIAS_PARA_PAGAR]
    esperado = sum(item["numero"] for item in abertas_esperadas)

    etapa("Dados de entrada")
    abrir_no_bloco_de_notas(DADOS, 3, contagem=True)

    PERFIL.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PERFIL), channel="msedge", headless=False, no_viewport=True, accept_downloads=True,
            args=["--start-maximized"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            entrar(page)
            cadastrar_fornecedores(page, linhas)
            lancar_contas(page, linhas)
            pagas = dar_baixa(page)
            valores = exportar_relatorio(page)
            page.click("#menu-contas")
            total_erp = page.inner_text("#total-aberto").replace("\xa0", " ")
            resultado = somar_na_calculadora(valores)
            time.sleep(1)
        finally:
            ctx.close()

    etapa("Resumo")
    log(f"Fornecedores cadastrados: {len(linhas)}")
    log(f"Contas lançadas: {len(linhas)} | pagas: {pagas} | em aberto: {len(valores)}")
    log(f"Total em aberto no ERP: {total_erp}")
    log(f"Total pela Calculadora: {brl(resultado)}")
    log(f"Total conferido pelo robô: {brl(esperado)}")
    if pagas != len(linhas) - len(abertas_esperadas) or resultado != esperado:
        log("ERRO: os totais não batem")
        sys.exit(1)
    log(f"TOTAL EM ABERTO: {brl(esperado)}")


if __name__ == "__main__":
    main()
