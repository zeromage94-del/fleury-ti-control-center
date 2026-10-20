"""Inicializador Windows do executável gerado pelo PyInstaller.
O servidor escuta apenas 127.0.0.1; a interface abre no navegador padrão.
"""
from pathlib import Path
import os
import sys
import traceback


def show_error(message):
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, message[:1800], 'Fleury TI Control Center', 0x10)
        except Exception:
            pass


def main():
    try:
        import app
        folder = app.DATA / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        # UTF-8 é necessário para eventos/acentos portugueses no Windows.
        log = (folder / 'runtime.log').open('a', encoding='utf-8', buffering=1)
        sys.stdout = log
        sys.stderr = log
        app.main()
    except Exception:
        reason = traceback.format_exc()
        try:
            from pathlib import Path
            p = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'FleuryTIControlCenter' / 'erro_inicializacao.txt'
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(reason, encoding='utf-8')
            show_error('Não foi possível iniciar o aplicativo.\n\n' + reason[-1000:] + '\n\nVeja: ' + str(p))
        except Exception:
            show_error(reason)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
