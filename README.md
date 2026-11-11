# Robô ERP: cadastro de fornecedores (exemplo do Next Automate)

1. Abre o `dados.txt` no Bloco de Notas, para mostrar os dados, e conta 3 segundos.
2. Abre o `erp.html` no Edge (Playwright, perfil fixo em `%LOCALAPPDATA%\NextAutomate\robo-erp\perfil-edge`), vai em **Fornecedores**, limpa a lista e, para cada linha, clica em **Novo fornecedor**, preenche e salva.
3. Com o ERP aberto, abre a Calculadora por cima, soma os valores e confere com a conta do robô. Sai com erro se não bater.

`dados.txt`: `Razão social;CNPJ;E-mail;Categoria;Valor`, com a primeira linha de cabeçalho. Os CNPJs são fictícios.

Testar no PC: `nextautomate run` nesta pasta.
