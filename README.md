# Robô ERP: rotina de contas a pagar (exemplo do Next Automate)

1. Mostra o `dados.txt` no Bloco de Notas e conta 3 segundos.
2. Abre o ERP **Gestão Pro** (um site separado: https://xzmuh.github.io/gestao-pro/, parâmetro `sistema`) no Edge e entra com usuário e senha. O robô acha tudo pelo que aparece na tela: menu, nomes dos botões e rótulos dos campos.
3. **Fornecedores:** cadastra os 15 (Novo fornecedor > preenche > Salvar).
4. **Contas a pagar:** lança uma conta por fornecedor, com o vencimento do `dados.txt`.
5. **Pagamentos:** filtra as que vencem em até 7 dias e dá baixa em cada uma.
6. **Notas fiscais:** emite a nota de cada conta paga. A do fornecedor com CNPJ inválido é rejeitada e vira um **ALERTA** no painel do cliente.
7. **Relatório:** lê na tela as contas em aberto, sem baixar arquivo.
8. **Calculadora** por cima do ERP: soma o que ficou em aberto e confere com o ERP e com a conta do robô.

Cada etapa vai para o log, com uma foto da tela nos artefatos da execução. O log segue o padrão do painel: `=== Etapa ===`, `OK:`, `AVISO:`, `ERRO:` e `ALERTA:` (problema que alguém precisa resolver; abre um alerta crítico no painel).

`dados.txt`: `Razão social;CNPJ;E-mail;Categoria;Valor;Vence em (dias)`, com cabeçalho. Os CNPJs são fictícios.
