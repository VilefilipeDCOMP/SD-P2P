import socket
import logging
import os
import threading

from utils_cs1_csa import send_json, recv_json, send_file_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [V2-Concorrente] %(levelname)s [Thread-%(thread)d] — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


HOST = "0.0.0.0"
PORT = 9002
BACKLOG = 128

# Diretório onde estão os arquivos de teste
FILES_DIR = "./arquivos"

#------Contador de Clientes Ativos ------
# Protegido por Lock para acesso thread-safe
active_clients_lock = threading.Lock()
active_clients_count = 0


def handle_client(conn: socket.socket, addr: tuple) -> None:
    
    # -- Esta função tem exatamente a mesma lógica do V1, mas é chamada em uma thread separada, permitindo que o servidor aceite novos clientes enquanto esta thread ainda está transferindo dados.
    
    global active_clients_count

    # Incrementa o contador de clientes ativos com proteção de lock
    with active_clients_lock:
        active_clients_count += 1
        count_snapshot = active_clients_count

    logging.info(
        "Cliente conectado: %s:%d | Clientes simultâneos: %d",
        addr[0], addr[1], count_snapshot
    )

    try:
        # -- Recebe a requisição
        request = recv_json(conn)
        logging.info("Requisição de %s: %s", addr, request)

        op = request.get("op")
        if op != "GET":
            send_json(conn, {"ok": False, "error": f"Operação desconhecida: {op}"})
            return

        file_id = request.get("file_id", "")

        # -- Localiza o arquivo e evita path traversal
        safe_name = os.path.basename(file_id)
        file_path = os.path.join(FILES_DIR, safe_name)

        if not os.path.isfile(file_path):
            logging.warning("Arquivo não encontrado: %s (cliente: %s)", file_path, addr)
            send_json(conn, {"ok": False, "error": f"Arquivo '{safe_name}' não encontrado."})
            return

        file_size = os.path.getsize(file_path)
        logging.info("Enviando '%s' (%d bytes) para %s", safe_name, file_size, addr)

        send_json(conn, {"ok": True, "size": file_size})

        # -- Transmissão dos dados
        send_file_chunks(conn, file_path, file_size)

        logging.info("Envio concluído para %s:%d", addr[0], addr[1])

    except ConnectionError as e:
        logging.warning("Conexão encerrada prematuramente por %s: %s", addr, e)
    except Exception as e:
        logging.error("Erro ao atender %s: %s", addr, e, exc_info=True)
    finally:
        conn.close()

        # Decrementa o contador de clientes ativos
        with active_clients_lock:
            active_clients_count -= 1
            remaining = active_clients_count

        logging.info(
            "Conexão fechada: %s:%d | Clientes restantes: %d",
            addr[0], addr[1], remaining
        )


def main():
    # ---Criar socket TCP---
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(BACKLOG)

    logging.info("=" * 60)
    logging.info("Servidor V2 (Concorrente) iniciado em %s:%d", HOST, PORT)
    logging.info("Diretório de arquivos: %s", os.path.abspath(FILES_DIR))
    logging.info("Modo: thread por cliente (ilimitado)")
    logging.info("=" * 60)

    try:
        while True:
            conn, addr = server_sock.accept()

            t = threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
                name=f"ClientThread-{addr[0]}:{addr[1]}"
            )
            t.start()

    except KeyboardInterrupt:
        logging.info("Servidor V2 encerrado pelo operador (Ctrl+C).")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()