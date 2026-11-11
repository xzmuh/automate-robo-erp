# Robô ERP: rotina de contas a pagar (exemplo do Next Automate)

1. Mostra o `dados.txt` no Bloco de Notas e conta 3 segundos.
2. Abre o `erp.html` no Edge e entra com usuário `robo` e senha `next123`.
3. **Fornecedores:** cadastra os 15 (Novo fornecedor > preenche > Salvar).
4. **Contas a pagar:** lança uma conta por fornecedor, com o vencimento do `dados.txt`.
5. **Pagamentos:** filtra as que vencem em até 7 dias e dá baixa em cada uma.
6. **Relatório:** exporta as contas em aberto para `Documentos\contas-em-aberto.csv` e abre no Bloco de Notas.
7. **Calculadora** por cima do ERP: soma o que ficou em aberto e confere com o ERP e com a conta do robô.

Cada etapa vai para o log, com uma foto da tela nos artefatos da execução.

`dados.txt`: `Razão social;CNPJ;E-mail;Categoria;Valor;Vence em (dias)`, com cabeçalho. Os CNPJs são fictícios.
