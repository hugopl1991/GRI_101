# pip install ruamel.yaml -- para preservar formatação/comentários é melhor do que reescrever o YAML com pyyaml puro

import argparse
import hashlib
import subprocess
import sys
import shutil
from pathlib import Path
import os
from ruamel.yaml import YAML

# Configurável via ambiente para execução em Azure
CONFIG_FILE = os.environ.get('CONFIG_FILE', 'config.yaml')  # Arquivo de configuração (padrão no repo)
RUNTIME_CONFIG_PATH = os.environ.get('RUNTIME_CONFIG_PATH', '/tmp/config.yaml')
AZURE_MODE = os.environ.get('AZURE_MODE', '0') == '1'
DEFAULT_BASE_YEAR = int(os.environ.get('DEFAULT_BASE_YEAR', '2020'))     # Ano base do processamento
DEFAULT_END_YEAR = int(os.environ.get('DEFAULT_END_YEAR', '2024'))      # Ano final do processamento
DEFAULT_AREA = os.environ.get('DEFAULT_AREA', 'PA')          # Estado de interesse - Ex: PA

BUILD_INPUT_FILES = ['Dockerfile', 'requirements.txt']
BUILD_HASH_FILE = '.build_hash'

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)

def parse_args():
    """Permite escolher os anos e a área via linha de comando, sem precisar editar o código."""
    parser = argparse.ArgumentParser(
        description="Orquestra o pipeline Veg_sec -> Down -> Burn -> Queimadas -> Borda -> Comparação."
    )
    parser.add_argument("--base-year", type=int, default=DEFAULT_BASE_YEAR,
                         help=f"Ano base para a comparação (default: {DEFAULT_BASE_YEAR})")
    parser.add_argument("--end-year", type=int, default=DEFAULT_END_YEAR,
                         help=f"Ano final para a comparação (default: {DEFAULT_END_YEAR})")
    parser.add_argument("--area", type=str, default=DEFAULT_AREA,
                         help="Estado de interesse (default: {DEFAULT_AREA})")
    parser.add_argument("--rebuild", action="store_true",
                         help="Força a reconstrução da imagem mesmo sem mudanças no Dockerfile/requirements.txt")
    return parser.parse_args()


def backup_config():
    """Cria uma cópia de segurança do config.yaml antes de qualquer alteração."""
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        print(f"[!] {CONFIG_FILE} não encontrado. Abortando.")
        sys.exit(1)

    backup_path = f"{CONFIG_FILE}.bak"
    try:
        shutil.copy(CONFIG_FILE, backup_path)
        print(f"[*] Backup criado em {backup_path}")
    except OSError as e:
        print(f"[!] Falha ao criar backup de {CONFIG_FILE}: {e}")
        sys.exit(1)

def restore_backup():
    """Restaura o config.yaml a partir do backup, usado quando uma etapa falha no meio do caminho."""
    backup_path = Path(f"{CONFIG_FILE}.bak")
    if backup_path.exists():
        shutil.copy(backup_path, CONFIG_FILE)
        print(f"[*] {CONFIG_FILE} restaurado a partir do backup após falha.")

def update_config_year(end_year, base_year_compare=None, area=None):
    """Lê, altera o end_year, opcionalmente o base_year_compare e a area no config.yaml, preservando formatação."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = yaml.load(f)

        if config is None:
            config = {}

        if 'Data' not in config:
            config['Data'] = {}

        config['Data']['end_year'] = end_year

        if base_year_compare is not None:
            config['Data']['base_year_compare'] = base_year_compare
            
        if area is not None:
            config['Data']['area'] = area

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            yaml.dump(config, f)

        print(f"[*] config.yaml atualizado: end_year={end_year}, base_year_compare={base_year_compare}, area={area}")

    except Exception as e:
        print(f"[!] Erro ao atualizar {CONFIG_FILE}: {e}")
        restore_backup()
        sys.exit(1)

def _compute_build_hash():
    """Calcula um hash combinado do Dockerfile + requirements.txt."""
    hasher = hashlib.sha256()
    for filename in BUILD_INPUT_FILES:
        path = Path(filename)
        if path.exists():
            hasher.update(path.read_bytes())
        else:
            hasher.update(f"MISSING:{filename}".encode())
    return hasher.hexdigest()

def needs_rebuild(force=False):
    """
    Retorna True apenas se o Dockerfile ou o requirements.txt mudaram desde
    o último build bem-sucedido (comparando um hash salvo em .build_hash),
    se --rebuild foi passado explicitamente, ou se ainda não há registro de
    build anterior. Isso evita reconstruir a imagem em toda execução do
    pipeline.
    """
    if force:
        print("[*] --rebuild solicitado: build forçado.")
        return True

    current_hash = _compute_build_hash()
    hash_path = Path(BUILD_HASH_FILE)

    if not hash_path.exists():
        print("[*] Nenhum build anterior registrado: build necessário.")
        return True

    previous_hash = hash_path.read_text().strip()
    if current_hash != previous_hash:
        print("[*] Dockerfile/requirements.txt mudaram desde o último build: build necessário.")
        return True

    print("[*] Dockerfile/requirements.txt inalterados: reaproveitando imagem existente.")
    return False

def _save_build_hash():
    Path(BUILD_HASH_FILE).write_text(_compute_build_hash())

def run_docker_compose(compose_file, build=False):
    """Executa o docker compose e aguarda a finalização."""
    print(f"[*] Iniciando os serviços do {compose_file}...")
    cmd = ["docker", "compose", "-f", compose_file, "up", "--force-recreate"]
    if build:
        cmd.insert(-1, "--build")

    try:
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1
        )
        for line in process.stdout:
            print(line, end="")
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)
        print(f"[*] Processamento do {compose_file} concluído com sucesso.\n")
    except subprocess.CalledProcessError as e:
        print(f"[!] Erro ao executar {compose_file}: {e}")
        restore_backup()
        sys.exit(1)

def cleanup_environment(compose_files):
    """Remove containers/órfãos de uma execução anterior antes de começar o pipeline."""
    for compose_file in compose_files:
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down", "--remove-orphans"],
            check=False
        )

if __name__ == "__main__":
    args = parse_args()

    # Em AZURE_MODE não alteramos o repo; geramos config de runtime
    if not AZURE_MODE:
        backup_config()
        cleanup_environment(["docker-compose_raster.yml", "docker-compose_table.yml"])
    else:
        base_cfg = {}
        repo_cfg_path = Path('config.yaml')
        try:
            if repo_cfg_path.exists():
                with open(repo_cfg_path, 'r', encoding='utf-8') as f:
                    base_cfg = yaml.load(f) or {}
        except Exception:
            base_cfg = {}

        if 'Paths' not in base_cfg:
            base_cfg['Paths'] = {}
        if 'Data' not in base_cfg:
            base_cfg['Data'] = {}

        # Prioriza valores vindos das variáveis/args
        base_cfg['Data']['base_year_compare'] = args.base_year
        base_cfg['Data']['end_year'] = args.end_year
        base_cfg['Data']['area'] = args.area or os.environ.get('AREA', base_cfg['Data'].get('area', DEFAULT_AREA))

        # Escreve config de runtime e aponta CONFIG_FILE para ele
        try:
            # 1) arquivo temporário (opcional)
            with open(RUNTIME_CONFIG_PATH, 'w', encoding='utf-8') as f:
                yaml.dump(base_cfg, f)
            # 2) também sobrescreve o config.yaml no diretório de trabalho
            with open(repo_cfg_path, 'w', encoding='utf-8') as f:
                yaml.dump(base_cfg, f)

            CONFIG_FILE = str(repo_cfg_path)
            print(f"[*] AZURE_MODE ativo: config de runtime escrito em {RUNTIME_CONFIG_PATH} e em {repo_cfg_path}")
        except Exception as e:
            print(f"[!] Falha ao escrever config runtime: {e}")
            sys.exit(1)


    # Decide UMA vez, no início, se a imagem precisa ser reconstruída.
    # Se sim, o build acontece apenas na primeira chamada abaixo — as
    # demais reaproveitam a imagem recém-criada, sem passar --build de novo.
    build_needed = needs_rebuild(force=args.rebuild)

    # 1. Rodar a sequência do ano base
    update_config_year(args.base_year, area=args.area)
    run_docker_compose("docker-compose_raster.yml", build=build_needed)
    if build_needed:
        _save_build_hash()
        build_needed = False  # já reconstruída; próximas chamadas reaproveitam

    # 2. Rodar a sequência do ano final
    update_config_year(args.end_year, area=args.area)
    run_docker_compose("docker-compose_raster.yml", build=build_needed)

    # 3. Rodar o script de comparação (base vs final)
    # docker-compose_table.yml usa a mesma imagem (npi-geo:latest) já
    # construída acima, então nunca precisa de --build aqui.
    update_config_year(args.end_year, base_year_compare=args.base_year, area=args.area)
    run_docker_compose("docker-compose_table.yml")