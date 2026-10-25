# Integrações

## Drivers Zebra e Downloads

Consulte [DRIVERS_ZEBRA.md](DRIVERS_ZEBRA.md) para configurar `FLEURY_ZEBRA_DRIVER_REPOSITORY`. O catálogo não instala pacotes; a troca confirmada usa um driver revisado já instalado no computador da fila.

A limpeza de Downloads fica em Scripts, separada de TEMP. Consulte a prévia, selecione os arquivos antigos e clique em Excluir selecionados: a exclusão definitiva começa diretamente, sem confirmação adicional. Ela cobre apenas pastas Downloads padrão de perfis locais não especiais; não segue redirecionamentos, links ou pastas de rede. Máximo de 200 candidatos por prévia, 12000 itens e seis níveis de inspeção; resultados limitados ou com falhas são informados como parciais. A prévia expira em cinco minutos e é consumida antes da execução; não há repetição automática após timeout.

## Zebra / zpl-rest

API conforme https://github.com/mrothenbuecher/zpl-rest: GET `/rest/printer`, GET `/rest/label`, POST `/rest/print` com `printer`, `label`, `data`.
O serviço externo precisa estar implantado pela TI; não é iniciado ou instalado pelo Fleury. Configure `FLEURY_ZPL_REST_URL` antes de abrir o aplicativo. HTTP apenas no loopback; HTTPS remoto com certificado confiável. Não aceita redirecionamentos. Portas HTTPS padrão são aceitas.

Na aba Integrações e Zebra, carregar catálogo, selecionar impressora/modelo e informar variáveis JSON. O servidor valida os IDs e bloqueia comandos ZPL nas variáveis; somente modelos revisados devem existir no zpl-rest. Confirmar antes de enviar. Conteúdo da etiqueta não aparece na auditoria. Sucesso indica aceitação do pedido; conferir etiqueta física. Timeout pode ocorrer após impressão: verificar fila antes de repetir.

O preview do projeto externo usa Labelary e envia ZPL a terceiros; o Fleury não chama esse endpoint. Não há reimpressão automática, reset ou calibração universal.

## Zammad

Fonte: https://github.com/zammad/zammad e https://docs.zammad.org/en/latest/api/ticket/index.html.
Defina `FLEURY_ZAMMAD_URL=https://...` e `FLEURY_ZAMMAD_TOKEN` apenas no ambiente da estação. Ative API/token na instância e conceda apenas acesso aos grupos necessários. A aba Atendimentos e a aba Integrações oferecem sincronização de leitura: até 300 tickets, atualizados pelo número externo. O aviso informa quando o limite possivelmente foi atingido. Atualização do status na fila Fleury permanece local. Não cria chamados nem envia notificações Zammad.

## WinUtil e aplicativos

Fonte: https://github.com/ChrisTitusTech/winutil (MIT). O catálogo Fleury usa WinGet por WinRM para instalar/desinstalar IDs predefinidos, com envio por clique e resultados por pacote. WinGet exige contexto compatível: não contornar bloqueio corporativo quando indisponível.

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

## v1.3: escopo, filas e descoberta

As rotas POST `/api/software/install` e `/api/software/uninstall` recebem alvo e chaves do catálogo e retornam HTTP 202 + `job_id` sem exigir `confirm`. A sessão/token local e validação de alvo continuam obrigatórios. `GET /api/software/jobs` retorna até 50 tarefas. Não existe execução PowerShell arbitrária enviada pelo cliente.

Operações WinGet usam `--scope machine --silent --disable-interactivity`; exigem identidade WinRM administrativa. Se o WinGet estiver instalado mas não estiver no PATH do WinRM, o cliente procura o executável no diretório padrão do DesktopAppInstaller sem mudar ACLs. Não há elevação, fallback por usuário ou mudanças em políticas. Instalações individuais já existentes em outros perfis não são removidas pelo uninstall por máquina; esse caso exige ferramenta corporativa com contexto apropriado.

A limpeza TEMP existente já percorre todos os perfis locais elegíveis. DNS, Spooler, restauração e manutenção do sistema são operações da máquina. Preferências e dados pessoais de cada usuário não são alterados por uma promessa genérica de todos os usuários.

`POST /api/machines/scan` aceita `mode=local`, `mode=segments` com lista `segments`, além dos modos anteriores. Na v1.3.2, a descoberta local usa a máscara real da interface. Até 8 segmentos privados, no máximo 4096 endereços únicos por operação (/20 ou menores). Redes maiores são rejeitadas com orientação para dividi-las; não há truncamento silencioso. A tabela de vizinhos é consultada após a varredura, incluindo dispositivos filtrados como não verificados. Detecção TCP cobre 5985,5986,3389,445,9100,631,443,80. Windows/SMB sugere computador; 9100/631 sem esses serviços sugere impressora. Isso não é identificação conclusiva do fabricante/SO. `POST /api/machines/classify` permite corrigir o tipo; alterações manuais são preservadas nas novas varreduras.
