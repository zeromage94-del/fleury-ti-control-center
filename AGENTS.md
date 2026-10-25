# Fleury TI Control Center

Aplicativo Python 3.12/stdlib + JavaScript sem framework, para Windows autorizado.

## Estrutura e execução

- `app.py`: servidor HTTP exclusivamente loopback, SQLite, autenticação por sessão e auditoria.
- `maintenance.py`, `software_catalog.py`, `admin_scripts.py`: operações PowerShell predefinidas.
- `integrations.py`: clientes externos e abertura de WinUtil local revisado.
- `static/`: interface; ordem de scripts definida em `index.html` é importante.
- `python app.py --no-browser`: servidor local, porta padrão 8765.
- `python -m unittest discover -s tests -v`: testes; não administrar máquinas reais durante testes.
- `node tests/ui_smoke.cjs`: carrega scripts em ordem e testa renderização/encadeamento de ações.
- `python build_windows.py --require-installer`: build Windows x64, exige Inno Setup 6.

## Regras de alteração

1. Vincule botões a ações e rotas reais; reporte falhas e limites com clareza.
2. Não habilite WinRM, TrustedHosts, GPO, firewall, execução irrestrita, nem desative EDR/antivírus automaticamente.
3. Use a identidade Windows existente. Nunca inclua senhas/tokens no navegador, repositório ou auditoria.
4. Software: o clique em Instalar/Desinstalar é a autorização, sem modal adicional, conforme pedido do proprietário. Valide computador, catálogo, sessão e escopo machine; registre fila, destino e resultado. Downloads: o clique em Excluir selecionados autoriza a exclusão, sem modal ou campo de confirmação adicional; preserve prévia, seleção, sessão, validade e auditoria. Outras operações de escrita preservam confirmação. Não registre ZPL ou conteúdo de etiquetas.
5. Não execute scripts obtidos de páginas externas automaticamente. WinUtil só por cópia local revisada e SHA256 configurado.
6. Não use preview Labelary para dados corporativos. Não execute testes de impressão/WinRM contra equipamentos reais sem destino de homologação informado.
7. Não inclua `data/`, bancos, fotos, logs, ambientes virtuais ou binários nos commits. Preserve o ZIP original fora do repositório.
8. Teste regressões relevantes com mocks. Build aprovado não equivale a homologação em Zebra/WinRM/Zammad real.
9. Respeite licenças de terceiros; preferir API a copiar código. Não inventar análise dos vídeos ou validação de hardware.
10. Mantenha `docs/STATUS.md` e tarefas atualizados com evidências reais.
