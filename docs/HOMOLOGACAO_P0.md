# Plano de homologação P0 — Windows / Zebra (ambiente isolado)

**Estado:** pendente de execução com equipamentos de homologação autorizados. Este roteiro **não** representa evidência de testes físicos ou WinRM/RDP reais. Nunca executar em produção.

## Preparação e segurança

1. Registrar responsável, data, commit, versão Windows 10/11 x64, PowerShell, WinGet, zpl-rest, modelo/firmware Zebra e rede/VLAN de laboratório.
2. Preparar duas VMs descartáveis: estação técnica e alvo Windows, com snapshot pré-teste e perfis fictícios distintos. Autorizar explicitamente os IPs/CIDRs; não usar faixas corporativas reais.
3. Habilitar somente as políticas WinRM/RDP já aprovadas para o laboratório. O Fleury não deve alterar firewall, TrustedHosts, GPO, EDR, antivírus nem ExecutionPolicy.
4. Configurar zpl-rest e impressora Zebra **de teste**, com mídia e dados fictícios. Nunca enviar dados de pacientes, etiquetas reais, tokens, senhas, IPs sensíveis ou capturas contendo informações pessoais.
5. Usar `python -m unittest discover -s tests -v` e `node tests/ui_smoke.cjs` antes da homologação manual. Os testes automatizados usam mocks; não substituem este roteiro.

## Matriz de execução e critérios

| ID | Ação em laboratório | Esperado / evidência não sensível |
|---|---|---|
| P0-01 | Cadastrar e selecionar VM Windows; selecionar impressora e dispositivo desconhecido em seguida | Seletores exibem classes corretas; comandos administrativos recusam impressoras e alvos não classificados como computador. |
| P0-02 | Descobrir vizinhos e segmento privado autorizado, incluindo máquina com ICMP bloqueado | Não duplicar IPv4 com MAC variável; serviços TCP podem indicar disponibilidade; equipamento filtrado aparece como não verificado, sem falso sucesso. Registrar contagens, não IPs. |
| P0-03 | Inventário, serviços, rede, desempenho, atualizações e impressoras via WinRM | Identidade Windows do técnico; respostas vinculadas ao alvo; falhas/timeout exibidos e auditados, sem elevar privilégios automaticamente. |
| P0-04 | Abrir RDP e PowerShell para VM cadastrada; tentar o mesmo com impressora | Abre somente para computador; autenticação necessária; impressora recusada antes de abrir processo. |
| P0-05 | Em dois perfis fictícios, criar arquivos `.tmp` antigos e recentes, mais `.txt` e arquivos em uso; executar limpeza pelo botão | Remove apenas `.tmp/.temp` antigos elegíveis nos TEMP previstos; preserva arquivos recentes, demais extensões e perfis; falha ou limite de 12.000 itens sinaliza resultado parcial. Conferir contadores e espaço. |
| P0-06 | Criar ponto de restauração, listar, tentar excluir sem pré-visualização, depois excluir ponto autorizado | Execução por clique sem confirmação adicional, validade da lista e ID vinculados à VM; sem apagar outros pontos. Snapshot da VM deve permitir recuperação independente. |
| P0-07 | Executar DISM/SFC/CHKDSK em VM descartável, com falha simulada e teste controlado | Código de saída não zero não pode ser registrado como sucesso; saída e auditoria coerentes; nenhum reparo em produção. |
| P0-08 | Com Zebra de homologação, consultar impressora/modelo e imprimir etiqueta fictícia via zpl-rest | Uma impressão por clique; conferir mídia, dimensão, driver e resultado físico; timeout não provoca reenvio automático. Não registrar ZPL, conteúdo da etiqueta ou token. |
| P0-09 | Simular indisponibilidade de WinRM, Spooler, zpl-rest e falhas de permissões | Interface exibe erro sem alegar sucesso; auditoria contém operação, alvo fictício e resultado, mas não credenciais, dados de etiquetas nem conteúdo sensível. |
| P0-10 | Instalar/desinstalar pacote de teste via WinGet em VM e reiniciar app durante uma tarefa controlada | Escopo `machine` obrigatório, fila por máquina, resultado por pacote; tarefa interrompida não é repetida automaticamente. Confirmar autorização e política da organização. |
| P0-11 | Em VM Windows limpa sem Python, executar ZIP portátil e instalador; fechar, reabrir e desinstalar | Portátil preserva `data/` ao lado do EXE; instalado preserva base em `%LOCALAPPDATA%\FleuryTIControlCenter\data`. Não contornar SmartScreen/EDR. |
| P0-12 | Verificar auditoria após sucesso, falha, timeout e operação parcial | Eventos correspondem ao observado; sem dados pessoais, senhas, tokens ou etiquetas. |

## Registro mínimo por cenário

- **ID e versão/commit:** 
- **Ambiente e autorização:** VM, Windows/serviço/modelo, sem nomes ou IPs corporativos.
- **Resultado esperado:** 
- **Resultado observado:** 
- **Evidência sanitizada:** log com segredo removido, screenshot fictícia ou hash do artefato.
- **Situação:** aprovado / reprovado / bloqueado / não executado.
- **Responsável e data:** 
- **Ação corretiva e issue/PR:** 

## Critérios de encerramento

A issue [P0 #1](https://github.com/zeromage94-del/fleury-ti-control-center/issues/1) permanece aberta até haver evidências de WinRM/RDP, limpeza e restauração reais **em laboratório autorizado**, mais impressão física Zebra com dados fictícios. O [workflow Windows](https://github.com/zeromage94-del/fleury-ti-control-center/actions) valida testes e binários, mas não substitui essas evidências. A issue [#3](https://github.com/zeromage94-del/fleury-ti-control-center/issues/3) controla a homologação do instalador e portátil em VM limpa.
