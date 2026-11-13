"""Robô de exemplo do Next Automate: rotina de contas a pagar num ERP.

1. Mostra o dados.txt no Bloco de Notas e conta 3 segundos.
2. Abre o ERP (um site, o parâmetro "sistema") no Edge e entra com usuário e senha.
   O robô acha tudo pelo que aparece na tela: textos do menu, nomes dos botões e
   rótulos dos campos, como uma pessoa faria.
3. Fornecedores: cadastra cada linha (Novo fornecedor > preenche > Salvar).
4. Contas a pagar: lança uma conta por fornecedor, com o vencimento do dados.txt.
5. Dá baixa nas contas que vencem em até 7 dias.
5b. Notas fiscais: emite a nota de cada conta paga. Nota rejeitada vira um
    ALERTA no painel do cliente, com o motivo e o que fazer.
6. Relatórios: lê na tela as contas em aberto, sem baixar arquivo.
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
import win32api
import win32con
import win32gui
from pywinauto import Desktop

PASTA = Path(__file__).resolve().parent
SISTEMA = os.environ.get("sistema") or "https://xzmuh.github.io/gestao-pro/"
USUARIO = os.environ.get("usuario") or "robo"
SENHA = os.environ.get("senha") or "next123"
DADOS = PASTA / "dados.txt"
# Perfil fixo do Edge: fica fora da pasta do robô, para sobreviver às versões novas.
PERFIL = Path(os.environ.get("PERFIL_EDGE") or
              Path(os.environ.get("LOCALAPPDATA", PASTA)) / "NextAutomate" / "robo-erp" / "perfil-edge")
PAUSA = float(os.environ.get("PAUSA", "0.4"))
DIAS_PARA_PAGAR = 7


def log(msg):
    print(msg, flush=True)


def etapa(titulo):
    log("")
    log(f"=== {titulo} ===")


def ok(msg):
    log(f"OK: {msg}")


def alerta(msg):
    log(f"ALERTA: {msg}")


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


def achar_janela(classe, titulo, segundos=5):
    fim = time.time() + segundos
    while time.time() < fim:
        achadas = []

        def ver(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetClassName(hwnd) == classe and re.search(titulo, win32gui.GetWindowText(hwnd)):
                achadas.append(hwnd)

        win32gui.EnumWindows(ver, None)
        if achadas:
            return achadas[0]
        time.sleep(0.1)
    return None


def trazer_para_frente(hwnd):
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32gui.SetForegroundWindow(hwnd)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
    except Exception:
        pass


def abrir_no_bloco_de_notas(arquivo, segundos, contagem=False):
    subprocess.Popen(["notepad.exe", str(arquivo)])
    janela = achar_janela("Notepad", re.escape(arquivo.stem))
    if janela:
        trazer_para_frente(janela)
    else:
        log("Bloco de Notas aberto, sem pegar o foco")
    for falta in range(segundos, 0, -1):
        if contagem:
            log(f"Começando em {falta}...")
        time.sleep(1)
    if janela:
        win32gui.PostMessage(janela, win32con.WM_CLOSE, 0, 0)


def tela(page):
    return page.locator("section:visible").first


def campo(page, rotulo):
    return tela(page).get_by_label(rotulo)


def botao(page, nome):
    return page.get_by_role("button", name=nome, exact=True).locator("visible=true").first


def menu(page, nome):
    page.locator("nav").get_by_text(nome, exact=True).click()
    log(f"Menu: {nome}")
    time.sleep(PAUSA)


def linhas_da_tabela(page):
    return tela(page).locator("table tbody tr").filter(has_not=page.locator("td.vazio"))


def valor_do_cartao(page, titulo):
    return tela(page).get_by_text(titulo, exact=True).locator("xpath=following-sibling::b").inner_text().replace("\xa0", " ")


def entrar(page):
    etapa("Login")
    page.goto(SISTEMA)
    log(f"Sistema: {SISTEMA}")
    campo(page, "Usuário").fill(USUARIO)
    campo(page, "Senha").fill(SENHA)
    time.sleep(PAUSA)
    botao(page, "Entrar").click()
    page.locator("nav").wait_for()
    log(f"Entrou no ERP como {USUARIO}")


def cadastrar_fornecedores(page, linhas):
    etapa("Fornecedores")
    menu(page, "Fornecedores")
    botao(page, "Limpar tudo").click()
    log("Dados da execução anterior apagados")
    for i, item in enumerate(linhas, 1):
        botao(page, "+ Novo fornecedor").click()
        campo(page, "Razão social").fill(item["razao"])
        campo(page, "CNPJ").fill(item["cnpj"])
        campo(page, "E-mail").fill(item["email"])
        campo(page, "Categoria").select_option(label=item["categoria"])
        campo(page, "Valor do contrato (R$)").fill(item["valor"])
        time.sleep(PAUSA / 2)
        botao(page, "Salvar fornecedor").click()
        linhas_da_tabela(page).nth(i - 1).wait_for()
        log(f"[{i:02d}/{len(linhas)}] fornecedor: {item['razao']} | {item['cnpj']}")
        time.sleep(PAUSA / 2)
    foto(page, "1-fornecedores")


def lancar_contas(page, linhas):
    etapa("Contas a pagar")
    menu(page, "Contas a pagar")
    for i, item in enumerate(linhas, 1):
        vencimento = date.today() + timedelta(days=item["dias"])
        botao(page, "+ Nova conta").click()
        campo(page, "Fornecedor").select_option(label=item["razao"])
        campo(page, "Descrição").fill(f"Contrato de {item['categoria'].lower()}")
        campo(page, "Vencimento").fill(vencimento.isoformat())
        campo(page, "Valor (R$)").fill(item["valor"])
        time.sleep(PAUSA / 2)
        botao(page, "Lançar conta").click()
        linhas_da_tabela(page).nth(i - 1).wait_for()
        log(f"[{i:02d}/{len(linhas)}] conta: {item['razao']} | vence {vencimento:%d/%m} | R$ {item['valor']}")
        time.sleep(PAUSA / 2)
    foto(page, "2-contas-lancadas")


def dar_baixa(page):
    etapa(f"Pagamentos (vencendo em até {DIAS_PARA_PAGAR} dias)")
    campo(page, "Vencendo em até (dias)").fill(str(DIAS_PARA_PAGAR))
    botao(page, "Filtrar").click()
    time.sleep(PAUSA)
    pagas = 0
    while True:
        botoes = tela(page).get_by_role("button", name="Dar baixa", exact=True).locator("visible=true")
        if botoes.count() == 0:
            break
        fornecedor = botoes.first.locator("xpath=ancestor::tr/td[1]").inner_text()
        botoes.first.click()
        pagas += 1
        log(f"Baixa: {fornecedor}")
        time.sleep(PAUSA)
    botao(page, "Mostrar todas").click()
    log(f"{pagas} contas pagas")
    foto(page, "3-pagamentos")
    return pagas


def emitir_notas(page):
    etapa("Notas fiscais das contas pagas")
    menu(page, "Notas fiscais")
    linhas = linhas_da_tabela(page)
    autorizadas, rejeitadas = 0, []
    for i in range(linhas.count()):
        linha = linhas.nth(i)
        fornecedor = linha.locator("td").nth(0).inner_text()
        linha.get_by_role("button", name="Emitir NF", exact=True).click()
        time.sleep(PAUSA)
        situacao = linhas.nth(i).locator("td").nth(2).inner_text().replace("\n", " ").strip()
        if "Autorizada" in situacao:
            autorizadas += 1
            ok(f"Nota fiscal de {fornecedor}: {situacao.lower()}")
        else:
            motivo = situacao.replace("Rejeitada", "").strip()
            rejeitadas.append(fornecedor)
            alerta(f"Nota fiscal de {fornecedor} não foi emitida. {motivo}. Corrija o CNPJ no cadastro do fornecedor e emita a nota de novo.")
    foto(page, "3b-notas-fiscais")
    return autorizadas, rejeitadas


def ler_relatorio(page):
    etapa("Relatório")
    menu(page, "Relatórios")
    texto = tela(page).locator("pre").inner_text()
    foto(page, "4-relatorio")
    valores = [linha.split(";")[-1] for linha in texto.splitlines()[1:] if linha.strip()]
    log(f"{len(valores)} contas em aberto no relatório")
    return valores


BOTOES_CALCULADORA = {str(n): f"num{n}Button" for n in range(10)} | {
    ",": "decimalSeparatorButton", "+": "plusButton", "=": "equalButton", "C": "clearButton"}


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
    hwnd = achar_janela("ApplicationFrameWindow", r"^(Calculadora|Calculator)$", 20)
    if not hwnd:
        raise SystemExit("a Calculadora não abriu")
    janela = Desktop(backend="uia").window(handle=hwnd)
    portugues = janela.window_text() == "Calculadora"
    janela.child_window(auto_id="plusButton", control_type="Button").wait("enabled", timeout=20)
    trazer_para_frente(hwnd)
    botoes = {tecla: janela.child_window(auto_id=auto_id, control_type="Button").wrapper_object()
              for tecla, auto_id in BOTOES_CALCULADORA.items()}

    def apertar(teclas):
        for tecla in teclas:
            botoes[tecla].invoke()
            time.sleep(0.05)

    apertar("C")
    log("Calculadora aberta por cima do ERP")
    for i, valor in enumerate(valores, 1):
        apertar("".join("," if c in ",." else c for c in valor.replace(".", "") if c in "0123456789,"))
        if i < len(valores):
            apertar("+")
        log(f"[{i:02d}/{len(valores)}] {valor}" + (" +" if i < len(valores) else ""))
        time.sleep(0.15)
    apertar("=")
    time.sleep(0.5)

    texto, resultado = ler_visor(janela, portugues)
    log(f"Visor: {texto}")
    time.sleep(4)
    win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
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
            str(PERFIL), channel="msedge", headless=False, no_viewport=True,
            args=["--start-maximized"])
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            entrar(page)
            cadastrar_fornecedores(page, linhas)
            lancar_contas(page, linhas)
            pagas = dar_baixa(page)
            notas, rejeitadas = emitir_notas(page)
            valores = ler_relatorio(page)
            menu(page, "Contas a pagar")
            total_erp = valor_do_cartao(page, "Total em aberto")
            resultado = somar_na_calculadora(valores)
            time.sleep(1)
        finally:
            ctx.close()

    etapa("Resumo")
    log(f"Fornecedores cadastrados: {len(linhas)}")
    log(f"Contas lançadas: {len(linhas)} | pagas: {pagas} | em aberto: {len(valores)}")
    log(f"Notas fiscais: {notas} autorizadas | {len(rejeitadas)} rejeitadas")
    log(f"Total em aberto no ERP: {total_erp}")
    log(f"Total pela Calculadora: {brl(resultado)}")
    log(f"Total conferido pelo robô: {brl(esperado)}")
    if pagas != len(linhas) - len(abertas_esperadas) or resultado != esperado:
        log(f"ERRO: os totais não batem. ERP {total_erp}, Calculadora {brl(resultado)}, robô {brl(esperado)}.")
        sys.exit(1)
    ok(f"Total em aberto conferido: {brl(esperado)}")
    if rejeitadas:
        log(f"AVISO: {len(rejeitadas)} nota(s) ficaram para emitir à mão: {', '.join(rejeitadas)}")


if __name__ == "__main__":
    main()
