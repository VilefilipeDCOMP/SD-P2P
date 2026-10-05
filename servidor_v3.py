"""
servidor_v3.py — Servidor Cliente-Servidor com Thread Pool (máx. N clientes)
=============================================================================
Disciplina : Sistemas Distribuídos — UFS
Atividade  : Avaliação de Desempenho na Transferência de Arquivo
Autores    : Dev 2
Porta      : 9003

Diferença em relação às outras versões:
  V1 -> 1 cliente por vez (loop sequencial)
  V2 -> 1 thread nova por cliente (concorrência ilimitada)
  V3 -> pool FIXO de N threads (concorrência limitada a N; padrão N = 2)

Como funciona:
  A thread principal só faz accept() e entrega a conexão ao pool
  (ThreadPoolExecutor). Se as N threads estiverem ocupadas, a conexão fica
  na fila interna do executor, SEM ser atendida: o cliente já enviou a
  requisição, mas só começa a receber a resposta quando uma thread do pool
  ficar livre. Por isso o tempo de espera na fila aparece no tempo medido
  pelo cliente, como exige a metodologia do experimento.

Protocolo (idêntico ao V1/V2, definido em utils_cs1_csA.py):
  [4 bytes big-endian = tamanho do JSON][JSON UTF-8][bytes binários]

Uso:
  python servidor_v3.py                 # N = 2
  POOL_SIZE=4 python servidor_v3.py     # para testar outro N (opcional)
"""

import logging
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor

from utils_cs1_csA import send_json, recv_json, send_file_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [V3-ThreadPool] %(levelname)s [%(threadName)s] — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = 9003
BACKLOG = 128

# Limite de clientes atendidos simultaneamente (decisão do grupo: N = 2)
POOL_SIZE = int(os.environ.get("POOL_SIZE", "2"))

# Diretório onde estão os arquivos de teste
FILES_DIR = "./arquivos"

# ─── Contador de clientes em atendimento (thread-safe) ────────────────────────
# Serve para comprovar nos logs que nunca passa de POOL_SIZE.
active_lock = threading.Lock()
active_count = 0


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """
    Atende um cliente. Mesma lógica do V1/V2; a diferença é que esta função
    roda dentro de uma das N threads do pool.

    Fluxo:
      1. Recebe a requisição JSON {"op":"GET","file_id":...}
      2. Valida a operação e localiza o arquivo (sem path traversal)
      3. Responde {"ok":true,"size":<tamanho real>} ou {"ok":false,"error":...}
      4. Envia exatamente `size` bytes do arquivo
      5. Fecha a conexão
    """
    global active_count

    with active_lock:
        active_count += 1
        snapshot = active_count
    logging.info("Atendimento iniciado: %s:%d | Em atendimento: %d/%d",
                 addr[0], addr[1], snapshot, POOL_SIZE)

    try:
        request = recv_json(conn)
        logging.info("Requisição de %s:%d: %s", addr[0], addr[1], request)

        op = request.get("op")
        if op != "GET":
            send_json(conn, {"ok": False, "error": f"Operação desconhecida: {op}"})
            return

        safe_name = os.path.basename(request.get("file_id", ""))
        file_path = os.path.join(FILES_DIR, safe_name)

        if not os.path.isfile(file_path):
            logging.warning("Arquivo não encontrado: %s", file_path)
            send_json(conn, {"ok": False, "error": f"Arquivo '{safe_name}' não encontrado."})
            return

        # O size enviado é sempre o tamanho REAL do arquivo em disco
        file_size = os.path.getsize(file_path)
        send_json(conn, {"ok": True, "size": file_size})
        send_file_chunks(conn, file_path, file_size)

        logging.info("Envio concluído: '%s' (%d bytes) para %s:%d",
                     safe_name, file_size, addr[0], addr[1])

    except ConnectionError as e:
        logging.warning("Conexão encerrada prematuramente por %s: %s", addr, e)
    except Exception as e:
        logging.error("Erro ao atender %s: %s", addr, e, exc_info=True)
    finally:
        conn.close()
        with active_lock:
            active_count -= 1
            remaining = active_count
        logging.info("Conexão fechada: %s:%d | Em atendimento: %d/%d",
                     addr[0], addr[1], remaining, POOL_SIZE)


def main() -> None:
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(BACKLOG)

    pool = ThreadPoolExecutor(max_workers=POOL_SIZE, thread_name_prefix="Worker")

    logging.info("=" * 60)
    logging.info("Servidor V3 (Thread Pool) iniciado em %s:%d", HOST, PORT)
    logging.info("Diretório de arquivos: %s", os.path.abspath(FILES_DIR))
    logging.info("Modo: no máximo %d clientes por vez (demais aguardam na fila)", POOL_SIZE)
    logging.info("=" * 60)

    try:
        while True:
            conn, addr = server_sock.accept()
            # submit() não bloqueia: se o pool estiver cheio, a conexão espera
            # na fila do executor até uma thread ficar livre.
            pool.submit(handle_client, conn, addr)

    except KeyboardInterrupt:
        logging.info("Servidor V3 encerrado pelo operador (Ctrl+C).")
    finally:
        server_sock.close()
        pool.shutdown(wait=False, cancel_futures=True)
        # Encerramento imediato: evita esperar transferências grandes em curso
        os._exit(0)


if __name__ == "__main__":
    main()
