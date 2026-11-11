# Robô ERP (exemplo do Next Automate)

Robô de tela de demonstração:

1. Abre o `erp.html` (um cadastro de clientes estilo ERP que grava no `localStorage`) no **Edge instalado**, com Playwright e um perfil fixo em `%LOCALAPPDATA%\NextAutomate\robo-erp\perfil-edge` (outra pasta com a variável `PERFIL_EDGE`).
2. Limpa a lista e cadastra as 15 linhas do `dados.txt` (`Nome;CPF;Valor`), com uma pausa curta entre elas (`PAUSA`, padrão 0,5 s).
3. Abre a Calculadora do Windows com pywinauto, digita a soma de todos os valores e confere o visor com a conta feita pelo robô. Sai com erro se não bater.

Cada passo e o total vão para o log. Ao fim, uma foto do ERP fica nos artefatos da execução (`erp.png`).

Os CPFs do `dados.txt` são fictícios (gerados só com dígitos verificadores válidos).

Testar no PC: `nextautomate run` nesta pasta.
