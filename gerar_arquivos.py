"""
Este script cria os arquivos binários de tamanho fixo utilizados nos experimentos de transferência, gerando bytes aleatórios, assim simulando dados reais e impedindo que o SO comprima os dados em trânsito.

Arquivos gerados no diretório ./arquivos/:
  - arquivo_5mb.bin   
  - arquivo_50mb.bin  
  - arquivo_500mb.bin 

"""

import os
import sys

# Diretório de saída
OUTPUT_DIR = "./arquivos"

FILES = [
    ("arquivo_5mb.bin",   5_000_000),   
    ("arquivo_50mb.bin",  50_000_000),   
    ("arquivo_500mb.bin", 500_000_000),  
]

# Tamanho de cada bloco gerado por iteração — 1 MB para eficiência
GENERATION_CHUNK = 1 * 1024 * 1024


def gerar_arquivo(caminho: str, tamanho: int) -> None:
    if os.path.exists(caminho):
        actual_size = os.path.getsize(caminho)
        if actual_size == tamanho:
            print(f"'{caminho}' já existe com tamanho correto ({tamanho:,} bytes).")
            return
        else:
            print(f"'{caminho}' existe mas com tamanho diferente. Recriando...")

    print(f"'{caminho}' ({tamanho:,} bytes)...", end="", flush=True)

    bytes_written = 0
    with open(caminho, "wb") as f:
        while bytes_written < tamanho:
            to_write = min(GENERATION_CHUNK, tamanho - bytes_written)
            f.write(os.urandom(to_write))
            bytes_written += to_write

    print(f"({bytes_written:,} bytes escritos)")


def main():
    print("=" * 60)
    print("  Gerador de Arquivos de Teste — SD-P2P")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Diretório de saída: {os.path.abspath(OUTPUT_DIR)}\n")

    total_size = 0
    for nome, tamanho in FILES:
        caminho = os.path.join(OUTPUT_DIR, nome)
        gerar_arquivo(caminho, tamanho)
        total_size += tamanho
        
    print("Geração concluída! Os servidores estão prontos para uso.")


if __name__ == "__main__":
    main()
