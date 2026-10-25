# Fleury TI Control Center 1.4.0

Central local de suporte Windows baseada no ZIP v1.2 fornecido pelo usuário. Python/stdlib, interface web local, SQLite e auditoria. Protótipo independente; não implica aprovação ou afiliação oficial do Grupo Fleury.

## Executar

Windows 10/11 x64, Python 3.12: `python app.py`. Abra http://127.0.0.1:8765.
Cadastre e selecione a máquina no topo. Ações remotas usam a identidade Windows do técnico e permissões WinRM/RDP existentes. O aplicativo não configura automaticamente firewall, TrustedHosts, EDR ou GPO.

## Novo na v1.4.0

- Downloads de todos os perfis locais: prévia, seleção individual e confirmação; separado da limpeza de TEMP. Arquivos recentes, alterados, protegidos e pastas redirecionadas são preservados.
- Diagnóstico de impressoras comuns/Zebra, resultado verificado da limpeza da fila e reinício do Spooler. Fila vazia não comprova correção de defeito físico.
- [Catálogo local revisado de drivers Zebra](docs/DRIVERS_ZEBRA.md), validação SHA256 de INF opcional e troca para driver compatível já instalado no computador.
- Verificação por TCP e ICMP; descoberta informa falhas individuais e atualiza computadores sem resposta.
- Instalações conferem pacote, escopo machine e código de saída; resultados parciais e necessidade de reinício aparecem na fila.
- Laboratório repetível: `python tests/run_simulated_lab.py`. [Cenários e limites](docs/VALIDACAO_1.4.0.md).

## Recursos da v1.3

- Catálogo visual por categorias, busca, seleção, recolher/expandir e consulta de instalados.
- Instalar/desinstalar com um clique: sem modal adicional, silencioso e em fila de segundo plano. Sessão local e identidade administrativa existente continuam obrigatórias.
- Escopo WinGet `machine` obrigatório; não há fallback para instalar apenas para o técnico. Apps sem suporte por máquina falham explicitamente. Não remove instalações individuais de outros perfis.
- Computadores, impressoras e desconhecidos em grupos separados nos seletores. Impressoras não recebem comandos Windows.
- Descoberta de vizinhos e até oito segmentos privados de 256 endereços cada, por ICMP e portas TCP. Dispositivos isolados ou filtrados podem não aparecer. Tipo detectado por portas é provável e pode ser corrigido pelo técnico.
- Fila persistente com deduplicação, resultado por pacote e recuperação de tarefas interrompidas sem repetir instalações automaticamente.

## Recursos

- Inventário, diagnósticos, RDP e console PowerShell remoto.
- TEMP de todos os perfis, pontos de restauração, DISM/SFC/CHKDSK e impressão, com confirmações.
- Catálogo WinGet: instalar/desinstalar até vinte pacotes por operação, em fila persistente, com relatório por pacote.
- Zebra/zpl-rest: impressoras, modelos e impressão confirmada por API, sem preview externo.
- Interface de aplicativos inspirada no WinUtil para computadores remotos; WinUtil original segue disponível por cópia local revisada, na estação do técnico.
- Zammad: importação de até 300 chamados por execução; status da fila Fleury continua local.
- Consultas de contas, Defender, firewall, eventos, boot e Windows Backup, além de inventário/rede/apps existentes.
- Atendimentos, patrimônio, indicadores e auditoria local.

Configuração e limites: [docs/INTEGRACOES.md](docs/INTEGRACOES.md). Configure as variáveis de `.env.example` no ambiente da estação; esse arquivo não é carregado automaticamente. Nunca envie tokens ao GitHub.

## Build Windows

Instale Python 3.12 x64 e Inno Setup 6 oficial. Execute `python build_windows.py --require-installer`.
O build instala o PyInstaller fixado em `requirements-build.txt` num ambiente isolado e gera em `entrega_windows/`:

- ZIP portátil com EXE, `_internal/` e marcador `PORTABLE_MODE`;
- instalador EXE Inno Setup;
- `SHA256.txt`.

O portátil precisa da pasta completa. Dados portáteis ficam ao lado do EXE em `data/`; a instalação usa `%LOCALAPPDATA%/FleuryTIControlCenter/data`. A desinstalação preserva esses dados. Binários não são assinados automaticamente.

O [workflow Windows](.github/workflows/windows.yml) executa testes e build em push para main, pull request, tag ou disparo manual. Resultados ficam nos **Artifacts** da execução; não há publicação automática de Release. Somente execução bem-sucedida confirma compilação.

## Trabalhar com Codex

Abra este repositório como projeto e siga [AGENTS.md](AGENTS.md). Não envie banco, fotos, logs ou credenciais ao GitHub. Prioridades: [docs/PRIORIDADES.md](docs/PRIORIDADES.md) e issues.

Testes: `python -m unittest discover -s tests -v` e `node tests/ui_smoke.cjs`.
Usam mocks para administração e serviços externos; não provam comunicação com hardware real. Validação: [docs/STATUS.md](docs/STATUS.md).

## Referências

- [WinUtil](https://github.com/christitustech/winutil): catálogo e abertura da cópia revisada.
- [zpl-rest](https://github.com/mrothenbuecher/zpl-rest): serviço externo Zebra/ZPL.
- [Zammad](https://github.com/zammad/zammad): helpdesk por API.
- [Vicarius](https://www.vicarius.io/articles/10-scripts-every-it-admin-should-have-in-their-toolbox): categorias administrativas implementadas localmente, sem copiar o artigo.

Código desses projetos não foi incorporado. Confira licenças antes de redistribuí-los. Marca, imagens e créditos do ZIP foram preservados; não foi adicionada uma licença que conceda direitos sobre esses materiais.
