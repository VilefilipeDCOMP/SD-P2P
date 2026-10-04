import sys
import os
import socket
import json
import threading

IP_ADDRESS = "127.0.0.1"
CHUNK_SIZE = 262144

def recv_exact(sock, numero_exato_bytes):
    dados_recebido = b""

    while len(dados_recebido) < numero_exato_bytes:
        parte = sock.recv(numero_exato_bytes - len(dados_recebido))

        if not parte:
            raise ConnectionError("Conexão encerrada antes de completar o prefixo")

        dados_recebido += parte

    return dados_recebido

def seed(sock, file_dir):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((IP_ADDRESS, 9011))
    sock.listen(5)

    print("[Seed] iniciado")
    if not file_dir:
        print("Erro: É necessário informar o arquivo a ser compartilhado")
        exit(1)
    if not os.path.isfile(file_dir):
        print(f"Erro: O arquivo '{file_dir}' não existe")
        exit(1)
    print(f"[Seed] Compartilhando o arquivo: {file_dir}")

    file_size = os.path.getsize(file_dir)

    chunks = []

    with open(file_dir, 'rb') as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            chunks.append(chunk)

    print(f"[Seed] Arquivo '{file_dir}' lido com sucesso. Tamanho: {len(chunks)} chunks.")

    while True:
        conn, addr = sock.accept()
        print(f"[Seed] Conexão recebida de {addr}")
    
        prefixo_recebido = recv_exact(conn, 4)
        tamanho_json = int.from_bytes(prefixo_recebido, "big")

        cabecalho_bytes = recv_exact(conn, tamanho_json)
        data = json.loads(cabecalho_bytes.decode("UTF-8"))

        op = data.get("op")

        match op:
            case "GET_BLOCK":
                block_id = data.get("block_id")

                if type(block_id) is not int:
                    print("[Seed] block_id deve ser um inteiro.")
                elif not ((block_id >= 0) and (block_id <= (len(chunks) - 1))):
                    print("[Seed] block_id inválido para arquivo desejado.")
                else:
                    bloco = chunks[block_id]

                    cabecalho = json.dumps({"status": "ok", "block_id": block_id, "size": len(bloco)})
                    cabecalho = cabecalho.encode("UTF-8")
                    prefixo = len(cabecalho).to_bytes(4, "big")

                    conn.sendall(prefixo)
                    conn.sendall(cabecalho)
                    conn.sendall(bloco)
            case "GET_METADADOS":
                cabecalho = json.dumps({"status": "ok", "file_size": file_size, "block_size": CHUNK_SIZE, "num_chunks": len(chunks)})
                cabecalho = cabecalho.encode("UTF-8")
                prefixo = len(cabecalho).to_bytes(4, "big")

                conn.sendall(prefixo)
                conn.sendall(cabecalho)


        conn.close()
        print(f"[Seed] Conexão com {addr} encerrada")

def peer_receive_chunk(sock, block_id):
    cabecalho = json.dumps({"op": "GET_BLOCK","block_id": block_id})
    cabecalho = cabecalho.encode("UTF-8")
    prefixo = len(cabecalho).to_bytes(4, "big")

    sock.sendall(prefixo)
    sock.sendall(cabecalho)

    ## Recebimento
    ## Prefixo
    prefixo_recebido = recv_exact(sock, 4)
    tamanho_json = int.from_bytes(prefixo_recebido, "big")

    ## Cabeçalho
    cabecalho_bytes = recv_exact(sock, tamanho_json)
    cabecalho_recebido = json.loads(cabecalho_bytes.decode("UTF-8"))
    block_id_recebido = cabecalho_recebido.get("block_id")

    ## Bloco
    bloco_recebido = recv_exact(sock, cabecalho_recebido.get("size"))

    return (block_id_recebido, bloco_recebido)

def peer_receive_meta(sock):
    cabecalho = json.dumps({"op": "GET_METADADOS"})
    cabecalho = cabecalho.encode("UTF-8")
    prefixo = len(cabecalho).to_bytes(4, "big")

    sock.sendall(prefixo)
    sock.sendall(cabecalho)

    ## Recebimento
    ## Prefixo
    prefixo_recebido = recv_exact(sock, 4)
    tamanho_json = int.from_bytes(prefixo_recebido, "big")

    ## Cabeçalho
    cabecalho_bytes = recv_exact(sock, tamanho_json)
    cabecalho_recebido = json.loads(cabecalho_bytes.decode("UTF-8"))


    file_size = cabecalho_recebido.get("file_size")
    block_size = cabecalho_recebido.get("block_size")
    num_chunks = cabecalho_recebido.get("num_chunks")

    return (file_size, block_size, num_chunks)

def peer_server(chunks, chunks_lock, id_peer):
    ## SERVIDOR
    sock_servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    mapeamento_peer = {
        "1": 9012,
        "2": 9013,
        "3": 9014,
        "4": 9015,
    }

    port = mapeamento_peer.get(id_peer) 

    if port is None:
        raise ValueError(f"ID de peer inválido: {id_peer}. Use valores de 1 a 4.")

    sock_servidor.bind((IP_ADDRESS, port))
    sock_servidor.listen(5)

    while True:
        conn, addr = sock_servidor.accept()
        print(f"[Peer {id_peer}] Conexão recebida de {addr}")
    
        prefixo_recebido = recv_exact(conn, 4)
        tamanho_json = int.from_bytes(prefixo_recebido, "big")

        cabecalho_bytes = recv_exact(conn, tamanho_json)
        data = json.loads(cabecalho_bytes.decode("UTF-8"))

        op = data.get("op")

        match op:
            case "GET_BLOCK":
                block_id = data.get("block_id")

                if type(block_id) is not int:
                    print(f"[Peer {id_peer}] block_id deve ser um inteiro.")
                elif block_id not in chunks:
                    print(f"[Peer {id_peer}] block_id inválido para arquivo desejado.")
                else:
                    with chunks_lock:
                        bloco = chunks.get(block_id)

                    cabecalho = json.dumps({"status": "ok", "block_id": block_id, "size": len(bloco)})
                    cabecalho = cabecalho.encode("UTF-8")
                    prefixo = len(cabecalho).to_bytes(4, "big")

                    conn.sendall(prefixo)
                    conn.sendall(cabecalho)
                    conn.sendall(bloco)

        conn.close()
        print(f"[Peer {id_peer}] Conexão com {addr} encerrada")
    
def peer(sock, id_peer):
    chunks = {}
    chunks_lock = threading.Lock()

    thread_servidor = threading.Thread(target=peer_server, args=(chunks, chunks_lock, id_peer))
    thread_servidor.start()
    
    ## CLIENTE
    print(f"[Peer {id_peer}] iniciado")

    sock.connect((IP_ADDRESS, 9011))

    (file_size, block_size, num_chunks) = peer_receive_meta(sock)
    print(file_size, block_size, num_chunks)

    sock.close()

    for i in range(0, num_chunks):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_bloco:
            sock_bloco.connect((IP_ADDRESS, 9011))

            block_id, bloco_recebido = peer_receive_chunk(sock_bloco, i)

            with chunks_lock:
                chunks[block_id] = bloco_recebido

    print(f"[Peer {id_peer}] Arquivo baixado!")



def peer_novo(sock, id_peer):
    chunks = {}
    
    ## CLIENTE
    print(f"[Peer {id_peer}] iniciado")

    sock.connect((IP_ADDRESS, 9012))
    block_id, bloco_recebido = peer_receive_chunk(sock, 5)

    print(block_id, len(bloco_recebido))
    chunks[block_id] = bloco_recebido 

    
    

if "__main__" == __name__:
    argv = sys.argv[1:]

    ## --tracker: Possui a lista de peers
    ## --seed: Possui o arquivo completo
    ## --peer: começa vazio e precisa baixar

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if argv[0] == "--seed":
        if len(argv) < 2:
            print("Erro: É necessário informar o arquivo a ser compartilhado")
            exit(1)
        else:
            seed(sock, sys.argv[2])
    elif argv[0] == "--peer":
        if len(argv) < 2:
            print("Erro: É necessário informar o id do cliente")
            exit(1)
        else:
            peer(sock, sys.argv[2])
    elif argv[0] == "--peer-recebimento":
        if len(argv) < 2:
            print("Erro: É necessário informar o id do cliente")
            exit(1)
        else:
            peer_novo(sock, sys.argv[2])

    
