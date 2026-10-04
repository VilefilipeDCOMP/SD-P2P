"""
utils.py — Utilitários de Comunicação TCP (Framing e I/O)
==========================================================
Disciplina : Sistemas Distribuídos — UFS
Atividade  : Avaliação de Desempenho na Transferência de Arquivo
Autores    : Dev 1
Data       : 2026

Este módulo centraliza toda a lógica de enquadramento (framing) de mensagens
TCP utilizada pelos servidores V1 e V2, evitando duplicação de código.

Por que framing?
----------------
O TCP é um protocolo de *stream* (fluxo contínuo de bytes). Ele não conhece
o conceito de "mensagem" — apenas entrega bytes em ordem, sem garantia de
que um único recv() devolva exatamente o que foi enviado num único send().
Fenômenos como "segmentação" (packet split) e "coalescência" (Nagle's
algorithm) podem partir ou juntar pacotes inesperadamente.

Solução adotada — Length-Prefix Framing:
  ┌─────────────────┬──────────────────────────────────────┐
  │  4 bytes (uint) │  payload JSON codificado em UTF-8    │
  │  big-endian     │  tamanho variável                    │
  └─────────────────┴──────────────────────────────────────┘

O receptor lê primeiro os 4 bytes para saber o tamanho exato e, em seguida,
acumula bytes em loop até receber o payload completo.
"""

import json
import struct
import socket
import logging

# ─── Constantes ──────────────────────────────────────────────────────────────

# Tamanho do cabeçalho de comprimento: 4 bytes representam um uint32
# suportando payloads de até ~4 GB — mais que suficiente para JSONs.
HEADER_SIZE = 4

# Formato struct: '!' = network byte order (big-endian), 'I' = unsigned int 32 bits
HEADER_FORMAT = "!I"

# Tamanho do bloco lido do disco durante o envio de dados binários.
# 64 KB é um valor clássico: grande o suficiente para I/O eficiente,
# pequeno o suficiente para não travar a memória RAM com arquivos grandes.
CHUNK_SIZE = 64 * 1024  # 64 KiB

# ─── Funções de Envio ─────────────────────────────────────────────────────────


def send_json(conn: socket.socket, data: dict) -> None:
    """
    Serializa `data` como JSON, codifica em UTF-8 e envia com framing.

    Fluxo:
      1. json.dumps → str  (serialização)
      2. str.encode('utf-8') → bytes  (codificação)
      3. struct.pack → 4 bytes de cabeçalho com o comprimento
      4. conn.sendall → envia cabeçalho + payload atomicamente

    Parâmetros:
        conn (socket.socket): Socket TCP conectado ao cliente.
        data (dict): Dicionário Python a ser enviado como JSON.

    Exceções:
        Propaga BrokenPipeError / ConnectionResetError se o cliente
        desconectar durante o envio — o chamador deve tratá-las.
    """
    payload = json.dumps(data).encode("utf-8")
    # struct.pack cria os 4 bytes de comprimento em ordem de rede
    header = struct.pack(HEADER_FORMAT, len(payload))
    # sendall garante que todos os bytes sejam enviados mesmo em caso de
    # envio parcial pelo kernel (situação comum em buffers cheios)
    conn.sendall(header + payload)


def recv_json(conn: socket.socket) -> dict:
    """
    Recebe uma mensagem com framing e retorna o dicionário Python.

    Fluxo:
      1. Recebe exatamente 4 bytes de cabeçalho
      2. Desempacota o comprimento do payload
      3. Loop recv() até acumular todos os bytes do payload
      4. Decodifica UTF-8 e faz json.loads

    Parâmetros:
        conn (socket.socket): Socket TCP conectado ao cliente.

    Retorna:
        dict: Dicionário Python decodificado do JSON recebido.

    Exceções:
        ConnectionError: Se o cliente fechar a conexão antes de enviar
                         os dados completos.
        json.JSONDecodeError: Se o payload não for JSON válido.
    """
    # ── Passo 1: ler o cabeçalho de 4 bytes ──────────────────────────────────
    raw_header = _recv_exactly(conn, HEADER_SIZE)
    if raw_header is None:
        raise ConnectionError("Conexão encerrada pelo cliente antes do cabeçalho.")

    # ── Passo 2: desempacotar o comprimento ───────────────────────────────────
    (length,) = struct.unpack(HEADER_FORMAT, raw_header)

    # ── Passo 3: ler o payload completo ──────────────────────────────────────
    raw_payload = _recv_exactly(conn, length)
    if raw_payload is None:
        raise ConnectionError("Conexão encerrada pelo cliente antes do payload completo.")

    # ── Passo 4: decodificar e retornar ──────────────────────────────────────
    return json.loads(raw_payload.decode("utf-8"))


def send_file_chunks(conn: socket.socket, file_path: str, file_size: int) -> None:
    """
    Envia o conteúdo binário de um arquivo em blocos (chunks).

    Por que chunks e não um único read()?
    - Arquivos de 500 MB exigiriam 500 MB de RAM apenas para o buffer.
    - Com chunks de 64 KB, o consumo de memória é constante e previsível.
    - O kernel pode fazer streaming eficiente via TCP send buffer.

    Parâmetros:
        conn (socket.socket): Socket TCP conectado ao cliente.
        file_path (str): Caminho absoluto ou relativo do arquivo no disco.
        file_size (int): Tamanho total esperado do arquivo em bytes
                         (usado apenas para logging; o loop lê até EOF).

    Exceções:
        FileNotFoundError: Se file_path não existir.
        Propaga exceções de socket em caso de falha de rede.
    """
    bytes_sent = 0
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                # EOF — arquivo completamente lido e enviado
                break
            conn.sendall(chunk)
            bytes_sent += len(chunk)

    logging.debug(
        "send_file_chunks: %d/%d bytes enviados de '%s'",
        bytes_sent,
        file_size,
        file_path,
    )


# ─── Função Auxiliar Interna ──────────────────────────────────────────────────


def _recv_exactly(conn: socket.socket, n: int) -> bytes | None:
    """
    Recebe exatamente `n` bytes do socket, acumulando em loop.

    O TCP pode entregar menos bytes do que o solicitado num único recv().
    Esta função resolve isso acumulando em um bytearray até completar `n`.

    Parâmetros:
        conn (socket.socket): Socket TCP conectado.
        n (int): Número exato de bytes a receber.

    Retorna:
        bytes: Os `n` bytes recebidos.
        None: Se a conexão for fechada (recv retorna b'').
    """
    buffer = bytearray()
    while len(buffer) < n:
        # Solicita apenas os bytes que ainda faltam para não ler além do esperado
        remaining = n - len(buffer)
        packet = conn.recv(remaining)
        if not packet:
            # Retorna None sinalizando desconexão limpa do cliente
            return None
        buffer.extend(packet)
    return bytes(buffer)
