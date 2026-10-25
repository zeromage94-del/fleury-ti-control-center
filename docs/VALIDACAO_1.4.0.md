# Validação v1.4 — laboratório corporativo simulado

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
| Downloads | Uma requisição sem prévia/seleção/idade/confirmar remove todos os arquivos de todos os perfis locais; inclui recentes, diversos formatos, somente leitura, ocultos, incompletos, mais de 200 arquivos e subpastas profundas. Testa arquivo bloqueado, junctions, sessão, alvo, concorrência e falhas parciais. |
| Impressoras | Laser comum com atolamento, Zebra sem mídia, filas bloqueadas/parcialmente removidas, preservação das outras filas e Spooler que não volta. Tratar a fila não elimina a falha física. |
| Drivers Zebra | Catálogo revisado, INF alterado, caminhos externos/links, driver não cadastrado, clique direto, resultado divergente e escolha de driver já instalado. |
| Software | Instalação, inventário e desinstalação de todos os pacotes do catálogo em lotes de até 20; sem admin, sem WinGet, máquina offline, timeout, código de falha, reinício requerido/iniciado, deduplicação e recuperação de interrupção. |
| Atendimento | Cadastro/classificação, patrimônio/imagens, CSV, chamados/SLA, indicadores, auditoria e sessão. |
| Outras funções | Consultas administrativas, console predefinido, restauração, DISM/SFC/CHKDSK, DNS, TEF, RDP/reinício, Zammad e Zebra REST com sucesso/falha simulados. |
| Interface | Renderização de todas as telas, catálogo único, carregamento/retry, exclusão integral de Downloads em um clique, troca de driver e 19 outros comandos sem autorização adicional, e exibição de resultados parciais. O DOM de teste não substitui navegação visual completa. |

No Windows, testes adicionais executam os scripts PowerShell de Downloads em perfis temporários e os scripts de impressão com cmdlets substituídos. Não usam perfis reais, impressoras, Spooler ou WinRM corporativos. Outro teste usa apenas o parser nativo para todos os scripts predefinidos.

## Binários

A v1.4.3 estende a execução direta a todos os comandos do Fleury. Os testes verificam chamadas sem `confirm`, ausência de modais de autorização, validação do alvo, falhas reais e auditoria. Cmdlets de escrita usam `-Confirm:$false`, e DISM usa `/NoRestart`.

Desde a v1.4.2 a limpeza de Downloads é integral. As versões anteriores tinham seleção/prévia; seus artefatos não incluem essa alteração.

O workflow `.github/workflows/windows.yml` executa testes no Windows Server 2022/Python 3.12, gera EXE portátil e instalador com PyInstaller/Inno Setup, inicia/reinicia o portátil e inicia o aplicativo instalado com dados fictícios via API loopback. Verifica assets, catálogo, persistência e preservação do banco após desinstalação; publica ZIP, instalador e SHA256 em Artifacts. Só a execução concluída do commit correspondente confirma o build.

Build v1.4.3 confirmado na [execução #14](https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40221511004), commit `0d3f874c98f4a4cb7b1f05d2c23fd1bb14e15115`: comandos diretos, testes nativos, geração e smoke dos binários aprovados. Baixe **Fleury-TI-Windows-x64** em Artifacts para obter o portátil, instalador e hashes; **Fleury-TI-Simulation-Report** contém o relatório Windows. Consulte `STATUS.md` para os digests dos artefatos.

Homologação em Windows 10/11 corporativo, drivers/firmware reais, qualidade de impressão, WinRM/WinGet, políticas e restauração permanecem necessárias conforme `HOMOLOGACAO_P0.md`.
