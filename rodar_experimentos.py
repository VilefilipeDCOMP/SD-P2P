import subprocess
import time
import csv

TAMANHOS = ['5MB.bin', '50MB.bin', '500MB.bin']
QTD_CLIENTES = [1, 5, 10, 20]
SERVIDORES = ['servidor_v1.py', 'servidor_v2.py']
ARQUIVO_SAIDA = 'resultados_brutos.csv'

def executar_experimentos():
    with open(ARQUIVO_SAIDA, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Servidor', 'Tamanho_Arquivo', 'Qtd_Clientes', 'ID_Cliente', 'Tempo_Segundos'])

        for servidor in SERVIDORES:
            for tamanho in TAMANHOS:
                for qtd in QTD_CLIENTES:
                    print(f"\nIniciando teste: {servidor} | {tamanho} | {qtd} clientes")

                    processo_servidor = subprocess.Popen(['python3', servidor])
                    time.sleep(2)

                    processos_clientes = []
                    for i in range(qtd):
                        p = subprocess.Popen(['python3', 'cliente_mock.py', tamanho], stdout=subprocess.PIPE, text=True)
                        processos_clientes.append((i, p))

                    for id_cliente, p in processos_clientes:
                        saida, _ = p.communicate()
                        tempo_gasto = saida.strip()
                        if tempo_gasto:
                            writer.writerow([servidor, tamanho, qtd, id_cliente, tempo_gasto])

                    processo_servidor.terminate()
                    processo_servidor.wait()

if __name__ == '__main__':
    executar_experimentos()
    print("\nExperimentos concluidos. Dados salvos em", ARQUIVO_SAIDA)
