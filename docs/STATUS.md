# Validação da migração

Data: 20/10/2026. Base: ZIP v1.2 do usuário.

## Verificado localmente

- Sintaxe Python dos módulos alterados.
- Dez testes com mocks: fechamento SQLite, URL/TLS, IDs Zebra, confirmação, variáveis sem comandos ZPL, redirecionamento, sigilo de tokens, hash WinUtil e auditoria.
- Oito testes existentes: catálogo, limpeza e proteção de pontos de restauração.
- Sete scripts JavaScript carregados juntos em ordem; todas as páginas renderizadas num DOM de teste; 48 referências de ações verificadas. Não equivale a teste visual em navegador.

## Validação pendente no ambiente real

- Testes HTTP existentes: sandbox bloqueou sockets (WinError 10013); primeira execução também falhou ao usar diretório temporário padrão no SQLite. Mantidos para execução no runner Windows. Não converter bloqueios em aprovação.
- Build Windows: conferir execução GitHub Actions. PyInstaller e Inno Setup não estavam instalados durante a inspeção inicial.
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
