"""
cliente_cs.py — Cliente Cliente-Servidor (download com medição e descarte)
===========================================================================
Disciplina : Sistemas Distribuídos — UFS
Atividade  : Avaliação de Desempenho na Transferência de Arquivo
Autores    : Dev 2

Faz UM download de um servidor C/S (V1, V2 ou V3), mede o tempo e descarta
o conteúdo recebido (nada é gravado em disco nem acumulado em memória).

Medição (metodologia do grupo):
  - O cronômetro (time.perf_counter) INICIA ANTES da conexão TCP.
  - O cronômetro PARA logo após o recebimento do último byte esperado.
  - Tempo de espera em fila (V1 e V3) entra na medição, pois a conexão e a
    requisição já foram feitas antes de o servidor começar a responder.
  - Inicialização dos processos e preparação dos arquivos ficam de fora.

Protocolo (idêntico ao dos servidores):
  1. Envia {"op":"GET","file_id":"..."}
  2. Recebe {"ok":true,"size":N} ou {"ok":false,"error":"..."}
  3. Lê exatamente N bytes; se a conexão fechar antes, é FALHA.

Saída padrão (stdout):
  - Sucesso: apenas o tempo em segundos (ex.: 1.234567), compatível com o
    formato que o rodar_experimentos.py já espera do cliente.
  - Falha: nada em stdout; mensagem em stderr e código de saída 1.
  - Com --json: sempre imprime uma linha JSON (inclusive nas falhas),
    útil para registrar falhas no CSV de resultados.

Exemplos:
  python cliente_cs.py --port 9003 --file arquivo_5mb.bin
  python cliente_cs.py --port 9001 --file arquivo_50mb.bin --esperado 50000000 --json
"""

import argparse
import json
import socket
import sys
import time

from utils_cs1_csA import send_json, recv_json

# Buffer ÚNICO e reaproveitado: cada recv_into sobrescreve o anterior, ou seja,
# o conteúdo é descartado na hora e o consumo de RAM é constante (64 KiB).
RECV_BUF_SIZE = 64 * 1024


def baixar(host: str, port: int, file_id: str, timeout: float, esperado: int | None) -> dict:
    """
    Executa um download e devolve um dicionário com o resultado.

    Chaves: ok, tempo_s, bytes_esperados, bytes_recebidos, erro.
    Nunca levanta exceção de rede: qualquer problema vira ok=False.
    """
    resultado = {
        "ok": False,
        "tempo_s": None,
        "bytes_esperados": None,
        "bytes_recebidos": 0,
        "erro": None,
    }

    buf = bytearray(RECV_BUF_SIZE)
    view = memoryview(buf)

    t_inicio = time.perf_counter()          # ← cronômetro começa ANTES de conectar
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            send_json(sock, {"op": "GET", "file_id": file_id})
            resposta = recv_json(sock)

            if not resposta.get("ok"):
                resultado["erro"] = f"servidor recusou: {resposta.get('error', 'sem motivo')}"
                return resultado

            size = resposta["size"]
            resultado["bytes_esperados"] = size

            if esperado is not None and size != esperado:
                resultado["erro"] = f"size divergente: servidor={size}, esperado={esperado}"
                return resultado

            recebidos = 0
            while recebidos < size:
                # Pede no máximo o que falta, para nunca ler além do arquivo
                n = sock.recv_into(view, min(RECV_BUF_SIZE, size - recebidos))
                if n == 0:
                    resultado["bytes_recebidos"] = recebidos
                    resultado["erro"] = (
                        f"conexão encerrada antes do fim ({recebidos}/{size} bytes)"
                    )
                    return resultado
                recebidos += n              # conteúdo descartado (buffer reaproveitado)

            t_fim = time.perf_counter()     # ← cronômetro para após o ÚLTIMO byte
            resultado["bytes_recebidos"] = recebidos
            resultado["tempo_s"] = t_fim - t_inicio
            resultado["ok"] = True
            return resultado

    except (OSError, ConnectionError, ValueError, KeyError) as e:
        # OSError cobre recusa de conexão, reset e timeout (socket.timeout)
        resultado["erro"] = f"{type(e).__name__}: {e}"
        return resultado


def main() -> int:
    p = argparse.ArgumentParser(description="Cliente C/S: baixa, mede o tempo e descarta.")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, required=True, help="9001 (V1), 9002 (V2) ou 9003 (V3)")
    p.add_argument("--file", required=True, dest="file_id", help="nome do arquivo no servidor")
    p.add_argument("--esperado", type=int, default=None,
                   help="tamanho esperado em bytes; se o servidor informar outro, conta como falha")
    p.add_argument("--timeout", type=float, default=600.0,
                   help="timeout (s) por operação de socket (padrão: 600)")
    p.add_argument("--json", action="store_true", help="imprime o resultado completo em JSON")
    args = p.parse_args()

    r = baixar(args.host, args.port, args.file_id, args.timeout, args.esperado)

    if args.json:
        print(json.dumps(r))
    elif r["ok"]:
        print(f"{r['tempo_s']:.6f}")

    if not r["ok"]:
        print(f"FALHA: {r['erro']}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
