# Validação da migração

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
