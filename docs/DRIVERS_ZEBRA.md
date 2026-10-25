# Repositório revisado de drivers Zebra

O Fleury oferece catálogo local, consulta dos drivers instalados e troca do driver de uma fila Zebra. Não redistribui todos os drivers do fabricante nem baixa/executa instaladores automaticamente. Use a [central oficial Zebra](https://www.zebra.com/us/en/support-downloads.html) para localizar a versão do modelo, arquitetura, Windows e linguagem de impressão.

Crie uma pasta fora do repositório e defina `FLEURY_ZEBRA_DRIVER_REPOSITORY` com seu caminho. Essa pasta contém `manifest.json`, com até 500 entradas. Exemplo que exige revisão antes de uso:

```json
{
  "packages": [
    {
      "id": "zd421-203-zpl",
      "title": "ZD421 203 DPI ZPL — referência local",
      "models": ["ZD421"],
      "driver_name": "ZDesigner ZD421-203dpi ZPL",
      "version": "Preencher com a versão revisada",
      "reviewed": false
    }
  ]
}
```

O nome do driver acima é ilustrativo: use o nome exato retornado por `Get-PrinterDriver` no computador de homologação. Confira o modelo físico, DPI, linguagem e versão, e somente então marque `reviewed: true`. Modelos são comparados como termos completos com o nome da fila/driver; renomear uma fila não comprova compatibilidade física. Não inclua segredos ou dados de etiquetas.

Entradas sem arquivo INF servem para trocar entre drivers já instalados. Para inventariar também um INF local, adicione `inf` (caminho relativo com `/`) e `sha256` (hash hexadecimal de 64 caracteres, calculado com `Get-FileHash -Algorithm SHA256`). O Fleury confere o hash a cada leitura, rejeita caminhos externos, links e arquivos alterados. Isso verifica somente o INF cadastrado; não valida os demais arquivos do pacote nem substitui assinatura digital do fabricante. Obtenção, verificação de assinatura e instalação do pacote continuam sob o procedimento da TI.

Na aba **Integrações e Zebra**, carregue o repositório, consulte os drivers e filas do computador, selecione a fila e o driver revisado já instalado, e confirme a troca. O servidor bloqueia modelos divergentes, drivers ausentes, Spooler parado e filas com trabalhos pendentes. Depois consulta o driver atual para verificar o resultado.

A troca não corrige cabeça de impressão, sensor, rolete, ribbon, rede ou mídia. Confira tamanho, DPI, linguagem e etiqueta física no equipamento de homologação. Não há calibração automática, envio de ZPL nem repetição após timeout.
