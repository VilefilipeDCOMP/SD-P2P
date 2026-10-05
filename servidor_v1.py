import socket
import logging
import os


from utils_cs1_csA import send_json, recv_json, send_file_chunks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [V1-Iterativo] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

HOST = "0.0.0.0" 
PORT = 9001
BACKLOG = 5

# Diretório onde estão os arquivos de teste 
FILES_DIR = "./arquivos"


def handle_client(conn: socket.socket, addr: tuple) -> None:
    """
    Fluxo:
      1. Recebe e valida a requisição JSON do cliente
      2. Localiza o arquivo solicitado no sistema de arquivos
      3. Envia resposta de sucesso com metadados (tamanho)
      4. Transmite os bytes do arquivo em chunks de 64 KB
      5. Fecha a conexão (o cliente sabe que recebeu tudo pelo tamanho)
    """
    logging.info("Cliente conectado: %s:%d", addr[0], addr[1])

    try:
        # -- Recebe a requisição
        request = recv_json(conn)
        logging.info("Requisição recebida: %s", request)

        op = request.get("op")
        if op != "GET":
            send_json(conn, {"ok": False, "error": f"Operação desconhecida: {op}"})
            return

        file_id = request.get("file_id", "")

        # -- Localiza o arquivo e evita path traversal
        safe_name = os.path.basename(file_id)
        file_path = os.path.join(FILES_DIR, safe_name)

        if not os.path.isfile(file_path):
            logging.warning("Arquivo não encontrado: %s", file_path)
            send_json(conn, {"ok": False, "error": f"Arquivo '{safe_name}' não encontrado."})
            return

        file_size = os.path.getsize(file_path)
        logging.info("Iniciando envio: %s (%d bytes)", safe_name, file_size)

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
        logging.info("Conexão fechada: %s:%d", addr[0], addr[1])


def main():
    # ---Criar socket TCP---
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(BACKLOG)

    logging.info("=" * 60)
    logging.info("Servidor V1 (Iterativo) iniciado em %s:%d", HOST, PORT)
    logging.info("Diretório de arquivos: %s", os.path.abspath(FILES_DIR))
    logging.info("Modo: 1 cliente por vez (monothread sequencial)")
    logging.info("=" * 60)

    try:
        while True:
            conn, addr = server_sock.accept()
            handle_client(conn, addr)

    except KeyboardInterrupt:
        logging.info("Servidor V1 encerrado pelo operador (Ctrl+C).")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()