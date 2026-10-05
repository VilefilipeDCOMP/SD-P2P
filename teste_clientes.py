"""
teste_clientes.py — dispara vários clientes ao mesmo tempo (teste manual)

Uso (na pasta do projeto, com o servidor já rodando em outro terminal):
  python teste_clientes.py --port 9003 --file arquivo_500mb.bin --esperado 500000000 --n 4

Cada cliente imprime o próprio tempo em segundos. Ao final, mostra
mínimo, médio e máximo.
"""
import argparse
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument("--port", type=int, required=True)
p.add_argument("--file", required=True)
p.add_argument("--esperado", type=int, required=True)
p.add_argument("--n", type=int, default=4, help="quantidade de clientes simultâneos")
args = p.parse_args()

# Inicia todos os clientes de uma vez
procs = [
    subprocess.Popen(
        [sys.executable, "cliente_cs.py",
         "--port", str(args.port), "--file", args.file,
         "--esperado", str(args.esperado)],
        stdout=subprocess.PIPE, text=True,
    )
    for _ in range(args.n)
]

# Espera todos terminarem e coleta os tempos
tempos = []
for proc in procs:
    saida, _ = proc.communicate()
    if proc.returncode == 0 and saida.strip():
        tempos.append(float(saida.strip()))
    else:
        print("um cliente FALHOU")

tempos.sort()
print("Tempos (s):", [round(t, 3) for t in tempos])
if tempos:
    print(f"mín={tempos[0]:.3f}  médio={sum(tempos)/len(tempos):.3f}  máx={tempos[-1]:.3f}")