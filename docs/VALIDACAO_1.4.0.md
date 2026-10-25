# Validação v1.4.0 — laboratório corporativo simulado

O laboratório usa HTTP loopback, SQLite e arquivos temporários reais. O adaptador de rede/WinRM mantém estado de computadores, pacotes e filas fictícias; qualquer processo ou conexão externa não modelada falha. Ele não é uma rede Windows corporativa real.

Execute na raiz:

```sh
python tests/run_simulated_lab.py
node tests/ui_smoke.cjs
```

O relatório `.test-temp/simulation-report.json` registra identificação e horário da execução, plataforma, cada teste/subteste, resultados esperados/observados e contagens separadas de aprovados, falhas e ignorados. O comando termina com erro se houver falhas ou nenhum teste. O workflow Windows preserva o relatório como artefato mesmo quando há falhas.

| Área | Cenários e resultado esperado |
| --- | --- |
| Descoberta | Todos os endereços de um segmento fictício são consultados; PCs com ICMP bloqueado aparecem por TCP; impressoras 631/9100 são separadas; máquina sem resposta perde estado Online; vizinhos ARP filtrados são preservados. |
| Rede lenta | Latência modelada de 400 ms, timeout, portas filtradas e erro por host; os demais resultados permanecem disponíveis. Limite existente: até oito segmentos privados, 4096 endereços únicos por operação. |
| PC lento | Pouca memória, disco cheio/eventos de armazenamento; TEMP de dois perfis com arquivo ocupado; resultado parcial não vira sucesso e documentos são preservados. Limpeza não garante ganho de desempenho. |
| Downloads | Perfis locais, seleção explícita, IDs opacos, sessão, confirmação, expiração, troca de alvo, arquivo alterado, repetição após timeout e preservação de itens não selecionados. |
| Impressoras | Laser comum com atolamento, Zebra sem mídia, filas bloqueadas/parcialmente removidas, preservação das outras filas e Spooler que não volta. Tratar a fila não elimina a falha física. |
| Drivers Zebra | Catálogo revisado, INF alterado, caminhos externos/links, driver não cadastrado, confirmação, resultado divergente e escolha de driver já instalado. |
| Software | Instalação, inventário e desinstalação de todos os pacotes do catálogo em lotes de até 20; sem admin, sem WinGet, máquina offline, timeout, código de falha, reinício requerido/iniciado, deduplicação e recuperação de interrupção. |
| Atendimento | Cadastro/classificação, patrimônio/imagens, CSV, chamados/SLA, indicadores, auditoria e sessão. |
| Outras funções | Consultas administrativas, console predefinido, restauração, DISM/SFC/CHKDSK, DNS, TEF, RDP/reinício, Zammad e Zebra REST com sucesso/falha simulados. |
| Interface | Renderização de todas as telas, catálogo único, carregamento/retry, seleção/confirmação de Downloads e driver, e exibição de resultados parciais. O DOM de teste não substitui navegação visual completa. |

No Windows, testes adicionais executam os scripts PowerShell de Downloads em perfis temporários e os scripts de impressão com cmdlets substituídos. Não usam perfis reais, impressoras, Spooler ou WinRM corporativos. Outro teste usa apenas o parser nativo para todos os scripts predefinidos.

## Binários

O workflow `.github/workflows/windows.yml` executa testes no Windows Server 2022/Python 3.12, gera EXE portátil e instalador com PyInstaller/Inno Setup, inicia/reinicia o portátil e inicia o aplicativo instalado com dados fictícios via API loopback. Verifica assets, catálogo, persistência e preservação do banco após desinstalação; publica ZIP, instalador e SHA256 em Artifacts. Só a execução concluída do commit correspondente confirma o build.

Esta documentação não declara aprovação prévia dos binários. Consulte o resultado da execução e o hash do commit antes de distribuir. Homologação em Windows 10/11 corporativo, drivers/firmware reais, qualidade de impressão, WinRM/WinGet, políticas e restauração permanecem necessárias conforme `HOMOLOGACAO_P0.md`.
