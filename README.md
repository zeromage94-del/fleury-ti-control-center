# Fleury TI Control Center 1.2.1

Central local de suporte Windows baseada no ZIP v1.2 fornecido pelo usuário. Python/stdlib, interface web local, SQLite e auditoria. Protótipo independente; não implica aprovação ou afiliação oficial do Grupo Fleury.

## Executar

Windows 10/11 x64, Python 3.12: `python app.py`. Abra http://127.0.0.1:8765.
Cadastre e selecione a máquina no topo. Ações remotas usam a identidade Windows do técnico e permissões WinRM/RDP existentes. O aplicativo não configura automaticamente firewall, TrustedHosts, EDR ou GPO.

## Recursos

- Inventário, diagnósticos, RDP e console PowerShell remoto.
- TEMP de todos os perfis, pontos de restauração, DISM/SFC/CHKDSK e impressão, com confirmações.
- Catálogo WinGet: instalar/desinstalar até cinco pacotes por operação e relatório por pacote.
- Zebra/zpl-rest: impressoras, modelos e impressão confirmada por API, sem preview externo.
- WinUtil original: janela separada usando cópia local revisada e SHA256; executa na estação do técnico.
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
