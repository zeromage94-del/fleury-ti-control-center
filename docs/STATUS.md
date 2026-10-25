# Estado atual: v1.3.2

25/10/2026: **v1.3.2 compilada e testada no Windows**, incluindo a correção da descoberta de vizinhos por IPv4 (PR #4, commit `c7b434911f598f54cc192509e2cddacaaae57328`). O [workflow Windows aprovado](https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40189673998) executou **62 testes Python**, regressões JavaScript, build portátil/instalador, inicialização/reinicialização do portátil, abertura do instalado, API loopback e preservação do SQLite na desinstalação. [Artefatos compilados](https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40189673998/artifacts/12596464419), expiração **08/11/2026 11:38:59 UTC**.

- `Fleury_TI_Portatil_v1.3.2_Windows_x64.zip`: SHA256 `439e84dbff90b0e70185c1847eaa8a4d8e27e4661039456510541acb7fd7f511`.
- `Fleury_TI_Instalador_v1.3.2_Windows_x64.exe`: SHA256 `37969a86f3edfd179d0633fc9d9e1f6804fd2e60c91a360915f69ade83d95977`.

[Relatório de simulação](VALIDACAO_1.3.2.md) e [roteiro de homologação P0](HOMOLOGACAO_P0.md). **Nenhuma validação em impressora física, WinRM/RDP corporativo, restauração real ou manutenção em produção foi realizada**. Issue P0 #1 permanece aberta. O histórico abaixo refere-se às versões anteriores.

# Validação da migração

## v1.4.0 — laboratório corporativo e remediação seletiva

Validação Linux em 25/10/2026: 109 testes descobertos, 102 aprovados e sete reservados ao Windows (parser PowerShell, três casos nativos de Downloads e três casos nativos de impressão). Relatório local da execução `f73fc6cd-cdd1-4b92-b6d2-941c0ab4aed4`: `.test-temp/simulation-report.json`; seis cenários sequenciais com 105 verificações esperadas/observadas. Oito scripts JS, todas as telas e 62 referências de ações; seleção/confirmação de Downloads, resultado parcial e driver revisado verificados no DOM de teste.

Instalação e desinstalação dos 47 pacotes do catálogo foram simuladas em lotes, com inventário e SQLite reais. Também foram exercitados bloqueio corporativo, ausência de admin/WinGet, timeout, falha parcial, descoberta com ping bloqueado e filas laser/Zebra. O adaptador mantém estado fictício, sem executar os instaladores de fornecedores.

Correções: verificação usa TCP/ICMP; falha de um host não descarta outros; cadastro sem resposta deixa de permanecer Online; fila valida IDs, escopo e códigos de saída; impressoras retornam estado verificado; Downloads tem prévia com IDs opacos, seleção, validade de cinco minutos e execução única. TEMP não inclui Downloads automaticamente e não segue junctions na raiz. Drivers Zebra vêm de catálogo local revisado; troca somente para driver já instalado e compatível com o modelo declarado.

Matriz e limites: [VALIDACAO_1.4.0.md](VALIDACAO_1.4.0.md). Homologação física e corporativa permanece pendente.

### Build v1.4.0 confirmado

- Commit compilado: `0662e31e6086f2bb8f16f37665e71fe1d02318cc`, branch `codex/corporate-simulation-1.4`. A `main` foi preservada.
- [Execução Windows #11](https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40203064667): **Success**, duração de 1m28s, em 25/10/2026.
- A execução aprovou as regressões Python/JS, incluindo os scripts nativos em sandbox Windows, compilou EXE e instalador e aprovou o smoke do portátil (abertura/reinício), aplicativo instalado, API local, assets e preservação do banco após desinstalação.
- Artefato **Fleury-TI-Windows-x64** (19 MB): contém ZIP portátil v1.4.0, instalador EXE e `SHA256.txt`. Digest SHA256 do artefato GitHub: `2527713814642c79855007e3875bc685e22d0f1953b8379ec90daddb17747ade`.
- Artefato **Fleury-TI-Simulation-Report** (8,59 KB): relatório JSON da execução Windows. Digest SHA256 do artefato: `331ace5a2ae806a657c9a95bf0558d4bec51eea5ecd6956298689b4eefbde281`.
- Esses digests identificam os contêineres de artefatos do GitHub; os hashes individuais do ZIP/EXE estão em `SHA256.txt`. Artefatos com retenção de 14 dias, sem publicação de Release.

Data: 20/10/2026. Base: ZIP v1.2 do usuário.

## Build Windows confirmado

Execução aprovada: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/39470794430

Commit compilado: `78ccf95b4db5ef068a9413655ab0e5ed46ba36f9`. Os 32 testes Python e o teste JavaScript passaram no runner Windows. PyInstaller e Inno Setup geraram os dois formatos e SHA256; o artefato foi enviado e confirmado na API do GitHub.

- Portátil: `Fleury_TI_Portatil_v1.2.1_Windows_x64.zip`, SHA256 `bc8b93c5c9db8ebce8064f0f0ff71d92d66a70a06c9b6bf13f3d248a368b7a80`.
- Instalador: `Fleury_TI_Instalador_v1.2.1_Windows_x64.exe`, SHA256 `c60e9cc80b7850bdcce56ea5633151b1eae20af2740e7834b328419fade0a83f`.
- Download: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/39470794430/artifacts/12286767549 (retenção de 14 dias).

A alteração subsequente do workflow apenas evita rebuild por documentação; não altera código do aplicativo. Instalação e execução dos binários em VM limpa ainda precisam de homologação, conforme issue #3.

## Verificado localmente

- Sintaxe Python dos módulos alterados.
- Dez testes com mocks: fechamento SQLite, URL/TLS, IDs Zebra, confirmação, variáveis sem comandos ZPL, redirecionamento, sigilo de tokens, hash WinUtil e auditoria.
- Oito testes existentes: catálogo, limpeza e proteção de pontos de restauração.
- Sete scripts JavaScript carregados juntos em ordem; todas as páginas renderizadas num DOM de teste; 48 referências de ações verificadas. Não equivale a teste visual em navegador.

## Validação pendente no ambiente real

- Testes HTTP existentes: sandbox local bloqueou sockets (WinError 10013). Foram executados com sucesso no runner Windows, após correção do fechamento SQLite.
- WinRM, RDP, Zebra, Zammad e WinUtil não executados em produção. Exigem configuração e homologação.
- Notas de vídeos herdadas do ZIP não comprovam reanálise nesta migração.

## Mudanças

- zpl-rest aceita HTTPS sem porta explícita, preserva IDs e inclui modelos/impressão confirmada.
- WinUtil por hash de cópia local, sem alterar ExecutionPolicy.
- Consultas administrativas fixas e auditadas.
- Resultado DISM/SFC/CHKDSK respeita código de saída.
- Atualização periódica preserva campos enquanto estão em edição.
- Corrigido vazamento de conexões SQLite: transação com commit/rollback e fechamento obrigatório, inclusive em exceções. O primeiro workflow revelou bloqueio do banco no encerramento dos testes Windows.
- README, AGENTS, workflow Windows, exclusões de dados locais e backlog.

## v1.3 com build aprovado

Implementados catálogo visual WinUtil remoto, fila assíncrona persistente, escopo machine obrigatório, classificação de dispositivos, seletores por grupo e descoberta ICMP/TCP multissegmento.

Verificação local: 41 testes Python aprovados; oito scripts JavaScript carregados e todas as telas renderizadas no teste de interface. No navegador, com base fictícia e execução remota substituída por simulação: clique em instalar enviou tarefa sem modal; impressora selecionada bloqueou instalação; fila mostrou conclusão. Nenhum aplicativo foi instalado em equipamento real durante esses testes.

Build v1.3 aprovado no commit `fdc2c11df3261aed5fa420f6a138e7cc8203c531`: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/39476581622

O runner Windows aprovou 41 testes Python, oito scripts JavaScript e renderização de todas as páginas, além de gerar e enviar os binários.

Download v1.3: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/39476581622/artifacts/12289103674

- `Fleury_TI_Portatil_v1.3_Windows_x64.zip`: SHA256 `3d7fbb4510d31ee30d7812fcc32147157bf5740ad3cbe9dc2308588bbe0912a7`.
- `Fleury_TI_Instalador_v1.3_Windows_x64.exe`: SHA256 `812a26fd73f0aaff2a3758e9508a15bb934e64c3729547727ee9a7c29850bff2`.

Artefatos com retenção de 14 dias. A execução em máquinas reais e a disponibilidade de WinGet/escopo machine no ambiente corporativo ainda precisam de homologação. Não foram realizados testes administrativos reais na rede do usuário.


## v1.3.1 — regressão simulada em 25/10/2026

Base revisada: 9b4f675137e7846211c546b8ac7a16540bef18ad.

- Reproduzidos e corrigidos: limpeza parcial registrada como sucesso; RDP/terminal/reinício sem exigência de computador identificado; detalhes de transporte Zammad expostos na auditoria.
- A limpeza agora devolve ok=false e partial=true quando há falhas ou limite de inspeção; a interface mostra alerta preservando os contadores.
- 56 testes Python descobertos: 55 aprovados localmente e um reservado ao parser PowerShell nativo do runner Windows. Cenários parametrizados cobrem consultas administrativas, scripts fixos, console, manutenção, RDP/terminal/reinício, seleção, descoberta simulada, fila de instalação/desinstalação, Zebra, Zammad paginado, CSV, chamados, patrimônio/imagens, indicadores e auditoria.
- Oito scripts JavaScript carregados, todas as páginas renderizadas e 56 referências de ações verificadas. Esse teste estrutural não comprova todos os cliques num navegador real.
- Testes novos bloqueiam processos e conectividade externa não simulados; usam SQLite e arquivos temporários reais, sem equipamentos corporativos.
- Workflow ampliado: parser PowerShell sem execução administrativa; abertura do portátil duas vezes, instalação silenciosa, abertura do EXE instalado, API loopback com registro fictício, imagem empacotada e preservação do banco após desinstalação. Resultado do novo build deve ser consultado no Actions; não pressupor aprovação antes da execução.

Limite: simulação não executa comandos administrativos contra Windows remoto, nem comprova impressão física, limpeza real, recuperação do Windows, WinGet corporativo ou políticas do domínio. P0 #1 continua pendente de homologação autorizada. Os binários ficam nos artefatos do workflow, não nos arquivos-fonte do Git.

### Build e execução dos pacotes v1.3.1 confirmados

- Commit testado/compilado: `b91a366813cd88e6ecec8ba1a1d3e52ffb2e616c`.
- Workflow concluído com sucesso: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40159259493
- Windows Server 2022 / Python 3.12: 56 testes aprovados, incluindo parser PowerShell nativo; oito scripts JS, renderização das páginas e 56 referências de ações verificadas.
- Smoke real dos executáveis no runner descartável aprovado: portátil iniciado e reiniciado, instalador silencioso executado, aplicativo instalado iniciado, API loopback com cadastro fictício, PNG empacotado e desinstalação preservando o banco. Nenhuma operação administrativa remota foi executada.
- Pacote com os dois formatos e SHA256.txt: https://github.com/zeromage94-del/fleury-ti-control-center/actions/runs/40159259493/artifacts/12584998943
- Portátil: `Fleury_TI_Portatil_v1.3.1_Windows_x64.zip`; SHA256 `2073a98ce42fe421f3d65941f62a3a697ecf334f6f52d105e57c1b663803976d`.
- Instalador: `Fleury_TI_Instalador_v1.3.1_Windows_x64.exe`; SHA256 `979ae34eba3e5a066724e112fca1d01e540f2222eda677792d042df7064d2ba9`.
- Expiração informada pela API: 08/11/2026 03:44:30 UTC (retenção de 14 dias).
- A validação no runner não substitui homologação Windows 10/11 corporativo, Zebra física, WinRM/RDP, WinGet e restauração em ambiente autorizado. A P0 permanece aberta.
