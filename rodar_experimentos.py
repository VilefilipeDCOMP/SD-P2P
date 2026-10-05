import argparse
import csv
import json
import os
import socket
import subprocess
import sys
import time

PYTHON = sys.executable
FILES_DIR = "./arquivos"
HOST = "127.0.0.1"

SERVIDORES = {
    "v1": {"script": "servidor_v1.py", "porta": 9001},
    "v2": {"script": "servidor_v2.py", "porta": 9002},
    "v3": {"script": "servidor_v3.py", "porta": 9003},
}

TAMANHOS = {
    "5MB":   {"arquivo": "arquivo_5mb.bin",   "bytes": 5_000_000},
    "50MB":  {"arquivo": "arquivo_50mb.bin",  "bytes": 50_000_000},
    "500MB": {"arquivo": "arquivo_500mb.bin", "bytes": 500_000_000},
}

QTD_CLIENTES = [1, 2, 4]
REPETICOES = 3
ARQUIVO_SAIDA = "resultados_brutos.csv"

COLUNAS = ["Servidor", "Tamanho_Arquivo", "Qtd_Clientes", "Repeticao",
           "ID_Cliente", "Tempo_Segundos", "Ok", "Bytes_Recebidos", "Erro"]


def verificar_arquivos(tamanhos):
    for nome in tamanhos:
        info = TAMANHOS[nome]
        caminho = os.path.join(FILES_DIR, info["arquivo"])
        if not os.path.isfile(caminho):
            sys.exit(f"Arquivo ausente: {caminho}. Rode 'python gerar_arquivos.py' antes.")
        real = os.path.getsize(caminho)
        if real != info["bytes"]:
            sys.exit(f"{caminho} tem {real} bytes, esperado {info['bytes']}. "
                     f"Rode 'python gerar_arquivos.py' novamente.")


def esperar_servidor(porta, processo, tentativas=100):
    for _ in range(tentativas):
        if processo.poll() is not None:
            sys.exit(f"O servidor da porta {porta} encerrou ao iniciar "
                     f"(código {processo.returncode}). Rode-o manualmente para ver o erro.")
        try:
            with socket.create_connection((HOST, porta), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)
    sys.exit(f"Servidor da porta {porta} não respondeu a tempo.")


def parar_servidor(processo):
    processo.terminate()
    try:
        processo.wait(timeout=5)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait()


def executar_cenario(writer, f, chave_srv, nome_tam, qtd, rep):
    srv = SERVIDORES[chave_srv]
    tam = TAMANHOS[nome_tam]

    servidor = subprocess.Popen([PYTHON, srv["script"]],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        esperar_servidor(srv["porta"], servidor)

        clientes = [
            subprocess.Popen(
                [PYTHON, "cliente_cs.py", "--host", HOST, "--port", str(srv["porta"]),
                 "--file", tam["arquivo"], "--esperado", str(tam["bytes"]), "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            for _ in range(qtd)
        ]

        for id_cliente, proc in enumerate(clientes, start=1):
            saida, _ = proc.communicate()
            try:
                r = json.loads(saida.strip().splitlines()[-1])
            except (ValueError, IndexError):
                r = {"ok": False, "tempo_s": None, "bytes_recebidos": 0,
                     "erro": "cliente não devolveu JSON"}
            writer.writerow([
                srv["script"], nome_tam, qtd, rep, id_cliente,
                f"{r['tempo_s']:.6f}" if r.get("tempo_s") is not None else "",
                r["ok"], r.get("bytes_recebidos", 0), r.get("erro") or "",
            ])
            f.flush()
    finally:
        parar_servidor(servidor)
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description="Benchmark C/S (V1, V2, V3)")
    ap.add_argument("--servidores", nargs="+", choices=SERVIDORES, default=list(SERVIDORES))
    ap.add_argument("--tamanhos", nargs="+", choices=TAMANHOS, default=list(TAMANHOS))
    ap.add_argument("--clientes", nargs="+", type=int, default=QTD_CLIENTES)
    ap.add_argument("--reps", type=int, default=REPETICOES)
    ap.add_argument("--saida", default=ARQUIVO_SAIDA)
    ap.add_argument("--rapido", action="store_true", help="só 5MB e 1 repetição (teste)")
    args = ap.parse_args()

    if args.rapido:
        args.tamanhos, args.reps = ["5MB"], 1

    verificar_arquivos(args.tamanhos)

    total = len(args.servidores) * len(args.tamanhos) * len(args.clientes) * args.reps
    feito = 0

    with open(args.saida, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUNAS)
        for chave in args.servidores:
            for nome_tam in args.tamanhos:
                for qtd in args.clientes:
                    for rep in range(1, args.reps + 1):
                        feito += 1
                        print(f"[{feito}/{total}] {SERVIDORES[chave]['script']} | {nome_tam} | "
                              f"{qtd} cliente(s) | repetição {rep}/{args.reps}", flush=True)
                        executar_cenario(writer, f, chave, nome_tam, qtd, rep)

    print(f"\nExperimentos concluídos. Dados salvos em {args.saida}")


if __name__ == "__main__":
    main()