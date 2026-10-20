# Integrações

## Zebra / zpl-rest

API conforme https://github.com/mrothenbuecher/zpl-rest: GET `/rest/printer`, GET `/rest/label`, POST `/rest/print` com `printer`, `label`, `data`.
O serviço externo precisa estar implantado pela TI; não é iniciado ou instalado pelo Fleury. Configure `FLEURY_ZPL_REST_URL` antes de abrir o aplicativo. HTTP apenas no loopback; HTTPS remoto com certificado confiável. Não aceita redirecionamentos. Portas HTTPS padrão são aceitas.

Na aba Integrações e Zebra, carregar catálogo, selecionar impressora/modelo e informar variáveis JSON. O servidor valida os IDs e bloqueia comandos ZPL nas variáveis; somente modelos revisados devem existir no zpl-rest. Confirmar antes de enviar. Conteúdo da etiqueta não aparece na auditoria. Sucesso indica aceitação do pedido; conferir etiqueta física. Timeout pode ocorrer após impressão: verificar fila antes de repetir.

O preview do projeto externo usa Labelary e envia ZPL a terceiros; o Fleury não chama esse endpoint. Não há reimpressão automática, reset ou calibração universal.

## Zammad

Fonte: https://github.com/zammad/zammad e https://docs.zammad.org/en/latest/api/ticket/index.html.
Defina `FLEURY_ZAMMAD_URL=https://...` e `FLEURY_ZAMMAD_TOKEN` apenas no ambiente da estação. Ative API/token na instância e conceda apenas acesso aos grupos necessários. A aba Atendimentos e a aba Integrações oferecem sincronização de leitura: até 300 tickets, atualizados pelo número externo. O aviso informa quando o limite possivelmente foi atingido. Atualização do status na fila Fleury permanece local. Não cria chamados nem envia notificações Zammad.

## WinUtil e aplicativos

Fonte: https://github.com/ChrisTitusTech/winutil (MIT). O catálogo Fleury usa WinGet por WinRM para instalar/desinstalar IDs predefinidos, com confirmação e resultados por pacote. WinGet exige contexto compatível: não contornar bloqueio corporativo quando indisponível.

Para abrir o WinUtil original, a TI deve obter e revisar uma versão fixa do script oficial, armazená-la localmente, calcular `Get-FileHash C:\TI\winutil.ps1 -Algorithm SHA256`, definir `FLEURY_WINUTIL_PATH` e `FLEURY_WINUTIL_SHA256`, e abrir o Fleury numa sessão com permissões adequadas. O botão verifica o hash e abre PowerShell separado, na estação do técnico. Não baixa e executa código da internet, não muda ExecutionPolicy e não aplica ações WinUtil à máquina remota selecionada. O Fleury registra somente a abertura.

## Biblioteca de scripts

Artigo de referência: https://www.vicarius.io/articles/10-scripts-every-it-admin-should-have-in-their-toolbox. O artigo descreve categorias e exemplos conceituais; não é um repositório de dez scripts prontos. A implementação local é própria.

| Categoria | Operação disponível |
|---|---|
| Reinicialização | Reinício confirmado na aba Comandos e consulta de boot/reinício pendente |
| Contas | Consulta de contas locais; sem provisionamento AD |
| Inventário | Hardware e aplicativos nas abas existentes |
| Limpeza | TEMP de todos os perfis, idade mínima e confirmação |
| Auditoria de segurança | Consulta do Microsoft Defender |
| Rede | Diagnóstico e ping de máquinas cadastradas |
| Firewall | Consulta dos perfis; sem alterações de regras |
| Implantação | Catálogo WinGet autorizado |
| Backup/restauração | Eventos Windows Backup e pontos de restauração; não substitui backup de arquivos |
| Logs | Erros de sistema das últimas 48 horas |

Consultas podem falhar quando componente, canal de eventos ou permissão não existir. A interface apresenta a falha e registra a tentativa.

## Licenças e dados

Integração por API não incorpora código dos projetos. WinUtil e zpl-rest declaram MIT; Zammad declara AGPLv3. Confira a licença da versão implantada antes de redistribuir ou modificar esses projetos. Conteúdo editorial Vicarius não foi copiado. Marca/imagens e autoria já existentes no ZIP foram preservadas; não implica afiliação oficial nem concede licença sobre marcas.
