# Validação v1.3.2 — 25/10/2026

## Resultado local

61 testes Python aprovados no Windows, incluindo subcenários de sucesso, falha e confirmação. O teste JavaScript carregou os oito scripts na ordem real, renderizou todas as páginas e verificou 56 referências de ações. Testes adicionais exercitaram carregamento de catálogo durante operação ocupada, requisições concorrentes, erro visível, nova tentativa e redirecionamento do menu antigo.

## Cenários simulados e resultados

| Área | Simulação | Resultado verificado |
|---|---|---|
| Catálogo | Abrir enquanto outra tarefa ocupa a interface; erro e retry | Uma requisição; programas renderizados; erro visível; recuperação |
| Rede | Interface /23, redes sobrepostas e limite /20 | Máscara preservada; endereços sem duplicação; excesso rejeitado explicitamente |
| Dispositivo filtrado | Vizinho ARP sem resposta ICMP/TCP | Cadastrado como não verificado, sem inventar disponibilidade |
| Computador lento | Resposta atrasada, CPU 98%, disco 100%, pouca RAM | Diagnóstico exibido pelo serviço sem tratar lentidão como sucesso de reparo |
| Impressão travada | Três trabalhos, estado Error, Spooler parado | Limpeza retorna três removidos; reinício retorna Running; nova consulta Normal |
| Software | Uma máquina aguardando e outra disponível | Fila continua na segunda máquina; ambos resultados persistidos |
| Falha/tempo limite | Spooler, limpeza de fila e SFC falham | Exceção e auditoria de falha; nenhum sucesso falso ou repetição automática |
| Código nativo | SFC retorna código 1 | Resultado ok=false |
| Consultas remotas | Inventário, impressoras, disco, desempenho, atualizações, serviços, rede, PINPAD, aplicativos; seis scripts e quatro consultas do console | Sucesso e falha com destino correto e auditoria |
| Manutenção | DNS, serviços, TEF, restauração, DISM, SFC, CHKDSK, temporários | Confirmação, erro, limpeza parcial, alvo e auditoria verificados |
| Acesso remoto | RDP, PowerShell e reinício | Computador selecionado; impressoras rejeitadas antes de abrir processo |
| Zebra/Zammad | Catálogo, impressão, indisponibilidade, paginação e reimportação | Falha auditada; sem conteúdo de etiqueta/token nos logs; limite de 300 informado |
| Dados locais | Chamados, CSV, SLA, classificação, inventário, anexos, indicadores e logs | Persistência SQLite e respostas verificadas |
| Windows scripts | Todos os scripts predefinidos analisados pelo parser PowerShell | Sintaxe aprovada; os scripts não são executados pelo teste |

## Correções

- Uma única entrada de aplicativos; o atalho antigo redireciona para ela.
- Carregamento do catálogo independente do bloqueio de ações administrativas, com deduplicação e erro visível.
- Descoberta usa máscara real, aceita até 4096 endereços privados e incorpora vizinhos após as sondagens; timeout TCP aumentado de 180 para 500 ms.
- Teste do pacote agora consulta o catálogo e o arquivo da interface no EXE portátil e instalado.

## Limites da evidência

Simulação executa Python, rotas, SQLite e JavaScript reais, substituindo transporte remoto e respostas de dispositivos. Não são VMs Windows com carga real nem impressoras físicas. Resultados simulados não comprovam reparo de hardware, compatibilidade de cada instalador WinGet, drivers, WinRM/GPO, impressão física ou descoberta de VLANs bloqueadas. Nenhum equipamento corporativo foi alterado.

O teste JavaScript usa DOM simulado; não comprova aparência em todas as resoluções. As ações de RDP/PowerShell são verificadas com processos simulados. O build e o teste dos binários ficam registrados na execução GitHub Actions correspondente a esta versão.
