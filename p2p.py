import sys
import os
import socket
import json
import threading
import random
import time

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

def send_msg(sock: socket.socket, resposta: dict):
    cabecalho = json.dumps(resposta)
    cabecalho = cabecalho.encode("UTF-8")
    prefixo = len(cabecalho).to_bytes(4, "big")

    sock.sendall(prefixo)
    sock.sendall(cabecalho)

def receive_msg(sock: socket.socket):
    ## Prefixo
    prefixo_recebido = recv_exact(sock, 4)
    tamanho_json = int.from_bytes(prefixo_recebido, "big")

    ## Cabeçalho
    cabecalho_bytes = recv_exact(sock, tamanho_json)
    cabecalho_recebido = json.loads(cabecalho_bytes.decode("UTF-8"))

    ## Bloco
    bloco_recebido = None
    
    if "size" in cabecalho_recebido:
        bloco_recebido = recv_exact(sock, cabecalho_recebido["size"])

    return (prefixo_recebido, cabecalho_recebido, bloco_recebido)

def seed(sock: socket.socket, file_dir):
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

    ## CONEXÃO COM TRACKER
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_tracker:
        sock_tracker.connect((IP_ADDRESS, 9010)) ## Conecta ao Tracker

        send_msg(sock_tracker, {"op": "REGISTER" , "peer_id": "seed", "port_peer": 9011})
        (prefixo_recebido, cabecalho_recebido, _) = receive_msg(sock_tracker)

        if cabecalho_recebido.get("status") != "ok":
            print("[Seed] Não foi possível registrar no tracker")
            exit(1)

        print("[Seed] Registrado no tracker!")

    for i in range(0, len(chunks)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_tracker:
            sock_tracker.connect((IP_ADDRESS, 9010))

            send_msg(sock_tracker, {"op": "HAVE" , "peer_id": "seed", "block_id": i})
            (prefixo_recebido, cabecalho_recebido, _) = receive_msg(sock_tracker)

            if cabecalho_recebido.get("status") != "ok":
                print("[Seed] Não foi possível registrar o bloco no tracker")
                exit(1)

    print("[Seed] Chunks registrados no tracker!")

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

def peer_receive_chunk(sock: socket.socket, block_id):
    send_msg(sock, {"op": "GET_BLOCK","block_id": block_id})

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

def peer_receive_meta(sock: socket.socket):
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
    
def peer(sock: socket.socket, id_peer):
    chunks = {}
    chunks_lock = threading.Lock()

    thread_servidor = threading.Thread(target=peer_server, args=(chunks, chunks_lock, id_peer))
    thread_servidor.start()
    
    ## CLIENTE
    print(f"[Peer {id_peer}] iniciado")

    sock_tracker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock_tracker.connect((IP_ADDRESS, 9010)) ## Conecta ao Tracker

    mapeamento_peer = {
        "1": 9012,
        "2": 9013,
        "3": 9014,
        "4": 9015,
    }

    port_peer = mapeamento_peer.get(id_peer) 

    send_msg(sock_tracker, {"op": "REGISTER" , "peer_id": id_peer, "port_peer": port_peer})
    (prefixo_recebido, cabecalho_recebido, _) = receive_msg(sock_tracker)

    if cabecalho_recebido.get("status") != "ok":
        print(f"[Peer {id_peer}] Não foi possível registrar o bloco no tracker")
        exit(1)

    sock_tracker.close()
    print(f"[Peer {id_peer}] Registrado no tracker!")

    ## OBTEM OS METADADOS DO SEED
    sock_seed = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    inicio_download = time.perf_counter()
    sock_seed.connect((IP_ADDRESS, 9011))

    (file_size, block_size, num_chunks) = peer_receive_meta(sock_seed)
    # print(file_size, block_size, num_chunks)

    sock_seed.close()

    for i in range(0, num_chunks):
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_tracker:
                sock_tracker.connect((IP_ADDRESS, 9010)) ## Conecta ao Tracker

                send_msg(sock_tracker, {"op": "GET_OWNERS", "peer_id": id_peer, "block_id": i})
                (_, cabecalho_recebido, _) = receive_msg(sock_tracker)

            if cabecalho_recebido.get("status") != "ok":
                print(f"[Peer {id_peer}] Não foi possível obter a listagem de todos seeders do chunk {i}")
                exit(1)

            ## Para que o Seed não seja escolhido tanto assim.
            seeders_lista = cabecalho_recebido.get("owners", [])
            seeders_lista = [
                dono for dono in seeders_lista
                if dono["peer_id"] != id_peer
            ]

            outros_peers = [
                dono for dono in seeders_lista
                if dono["peer_id"] != "seed"
            ]

            candidatos = outros_peers or seeders_lista

            if candidatos:
                break

            print(f"[Peer {id_peer}] Aguardando um dono do bloco {i}")
            time.sleep(0.5)

        seeder_escolhido = random.choice(candidatos)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_bloco:
            sock_bloco.connect((seeder_escolhido["ip"], seeder_escolhido.get("port")))

            block_id, bloco_recebido = peer_receive_chunk(sock_bloco, i)

        if i == (num_chunks - 1):
            fim_download = time.perf_counter()

        if type(block_id) is not int or block_id != i:
            raise ValueError(
                f"Bloco incorreto: solicitado {i}, recebido {block_id}"
            )

        with chunks_lock:
            chunks[block_id] = bloco_recebido

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock_tracker:
            sock_tracker.connect((IP_ADDRESS, 9010)) ## Conecta ao Tracker

            send_msg(sock_tracker, {"op": "HAVE" , "peer_id": id_peer, "block_id": block_id})
            (_, cabecalho_recebido, _) = receive_msg(sock_tracker)

            if cabecalho_recebido.get("status") != "ok":
                print("[Seed] Não foi possível registrar o bloco no tracker")
                exit(1)

    tempo_download = fim_download - inicio_download
    print(f"[Peer {id_peer}] Download conferido: {file_size} bytes em {tempo_download:.6f} segundos", flush=True)

    with chunks_lock:
        blocos_faltando = [i for i in range(num_chunks) if i not in chunks]

        total_bytes = sum(len(bloco) for bloco in chunks.values())

    if blocos_faltando:
        raise ValueError(f"Blocos faltando: {blocos_faltando}")

    if total_bytes != file_size:
        raise ValueError(f"Tamanho incorreto: esperado {file_size} bytes, recebido {total_bytes} bytes")

    print(f"[Peer {id_peer}] Arquivo baixado e conferido: {num_chunks} blocos, {total_bytes} bytes")

def tracker(sock: socket.socket):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((IP_ADDRESS, 9010))
    sock.listen(5)
    
    print("[Tracker] iniciado")

    registro_peer = {}

    while True:
        conn, addr = sock.accept()
        print(f"[Tracker] Conexão recebida de {addr}")

        prefixo_recebido = recv_exact(conn, 4)
        tamanho_json = int.from_bytes(prefixo_recebido, "big")

        cabecalho_bytes = recv_exact(conn, tamanho_json)
        data = json.loads(cabecalho_bytes.decode("UTF-8"))

        op = data.get("op")

        match op:
            case "REGISTER":
                peer_id = data.get("peer_id")
                port_peer = data.get("port_peer")

                if peer_id in registro_peer:
                    print("ERRO: Peer já cadastrado.")

                    resposta = {"status": "erro"}
                else:
                    registro_peer[peer_id] = {"ip": addr[0], "port": port_peer, "blocos": []}

                    resposta = {"status": "ok"}

                cabecalho = json.dumps(resposta)
                cabecalho = cabecalho.encode("UTF-8")
                prefixo = len(cabecalho).to_bytes(4, "big")

                conn.sendall(prefixo)
                conn.sendall(cabecalho)


            case "HAVE":
                peer_id = data.get("peer_id")
                block_id = data.get("block_id")

                if type(block_id) is not int or block_id < 0:
                    print("ERRO: block_id inválido.")
                    resposta = {"status": "erro"}
                elif peer_id not in registro_peer:
                    print("ERRO: peer não cadastrado.")
                    resposta = {"status": "erro"}
                else:
                    blocos = registro_peer[peer_id].setdefault("blocos", [])

                    if block_id not in blocos:
                        blocos.append(block_id)

                    resposta = {"status": "ok"}
                    

                cabecalho = json.dumps(resposta)
                cabecalho = cabecalho.encode("UTF-8")
                prefixo = len(cabecalho).to_bytes(4, "big")

                conn.sendall(prefixo)
                conn.sendall(cabecalho)

            case "GET_OWNERS":
                peer_id = data.get("peer_id")
                block_id = data.get("block_id")

                if type(block_id) is not int or block_id < 0:
                    print("ERRO: block_id inválido.")
                    resposta = {"status": "erro"}
                else:
                    owners = []

                    for id_cadastrado, registro in registro_peer.items():
                        if id_cadastrado == peer_id:
                            continue

                        if block_id in registro.get("blocos", []):
                            owners.append({
                                "peer_id": id_cadastrado,
                                "ip": registro["ip"],
                                "port": registro["port"]
                            })

                    resposta = {"status": "ok", "owners": owners}

                cabecalho = json.dumps(resposta)
                cabecalho = cabecalho.encode("UTF-8")
                prefixo = len(cabecalho).to_bytes(4, "big")

                conn.sendall(prefixo)
                conn.sendall(cabecalho)

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
    elif argv[0] == "--tracker":
        tracker(sock)