"""Gera portátil com .exe e instalador Inno Setup no Windows 10/11 x64.
Executar GERAR_EXE_WINDOWS.cmd. Não cria binários Windows em Linux.
"""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import venv
import zipfile

ROOT = Path(__file__).resolve().parent
VERSION = '1.4.2'
BIN = 'FleuryTIControlCenter.exe'
NAME = 'FleuryTIControlCenter'
OUT = ROOT / 'entrega_windows'


def run(args):
    print('>', ' '.join(map(str, args)), flush=True)
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def inno_compiler():
    candidates = [os.environ.get('INNO_SETUP_ISCC', ''),
                  r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
                  r'C:\Program Files\Inno Setup 6\ISCC.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def hashfile(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def main():
    if sys.platform != 'win32':
        raise SystemExit('A compilação de .exe para Windows requer executar este script em Windows 10/11 x64.')
    if '--require-installer' in sys.argv and not inno_compiler():
        raise SystemExit('Inno Setup 6 obrigatório neste build. Configure INNO_SETUP_ISCC.')
    OUT.mkdir(exist_ok=True)
    venv_dir = ROOT / '_venv_build'
    if not (venv_dir / 'Scripts' / 'python.exe').exists():
        print('Preparando ambiente de compilação, sem alterar o Python do sistema...')
        venv.EnvBuilder(with_pip=True).create(str(venv_dir))
    py = venv_dir / 'Scripts' / 'python.exe'
    run([py, '-m', 'pip', 'install', '-r', ROOT / 'requirements-build.txt'])

    run([py, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
         '--name', NAME, '--add-data', f'{ROOT / "static"};static',
         '--paths', ROOT, str(ROOT / 'launcher.py')])
    built = ROOT / 'dist' / NAME
    exe = built / BIN
    if not exe.is_file():
        raise SystemExit('PyInstaller não gerou o executável esperado.')

    portable = OUT / f'Fleury_TI_Portatil_v{VERSION}'
    if portable.exists():
        if portable.resolve().parent != OUT.resolve() or portable.is_symlink():
            raise SystemExit('Diretório portátil fora da pasta de entrega. Operação cancelada.')
        shutil.rmtree(portable)
    shutil.copytree(built, portable)
    (portable / 'PORTABLE_MODE').write_text('Mantém os dados no diretório data, ao lado do executável.\n', encoding='utf-8')
    (portable / 'data').mkdir(exist_ok=True)
    shutil.copy2(ROOT / 'LEIA_PRIMEIRO.txt', portable / 'LEIA_PRIMEIRO.txt')
    archive = OUT / f'Fleury_TI_Portatil_v{VERSION}_Windows_x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in portable.rglob('*'):
            if f.is_file():
                z.write(f, f.relative_to(OUT))
    print('PORTÁTIL GERADO:', archive)

    iscc = inno_compiler()
    if iscc:
        run([iscc, ROOT / 'instalador.iss'])
    else:
        print('INNO SETUP NÃO ENCONTRADO. O portátil já está pronto.')
        print('Instale Inno Setup 6 oficial e execute novamente para gerar o Setup.exe.')
        print('https://jrsoftware.org/isinfo.php')
    artifacts = [archive] + sorted(OUT.glob('Fleury_TI_Instalador_*.exe'))
    with (OUT / 'SHA256.txt').open('w', encoding='utf-8') as sums:
        for f in artifacts:
            line = f'{hashfile(f)}  {f.name}'
            print(line)
            sums.write(line + '\n')
    print('Arquivos finais:', OUT)


if __name__ == '__main__':
    main()
