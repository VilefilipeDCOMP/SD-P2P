"""
gerar_graficos.py - Dev 5
Gera graficos do relatorio a partir de estatisticas_finais.csv (saida do analise.py).

Uso:
    python gerar_graficos.py                  # usa estatisticas_finais.csv
    python gerar_graficos.py arquivo.csv      # CSV alternativo
    python gerar_graficos.py --demo           # dados simulados, sem CSV
"""

import os, sys, argparse, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# --- Mapeamentos de exibicao ---
NOMES = {
    "servidor_v1.py": "V1 - Iterativo",
    "servidor_v2.py": "V2 - Thread/Cliente",
    "servidor_v3.py": "V3 - Thread Pool (N=2)",
    "p2p":            "P2P",
}
CORES = {
    "servidor_v1.py": "#E05C5C",
    "servidor_v2.py": "#3B82F6",
    "servidor_v3.py": "#F0A500",
    "p2p":            "#22C55E",
}
ORDEM_SRV = ["servidor_v1.py", "servidor_v2.py", "servidor_v3.py", "p2p"]
ORDEM_TAM = ["5MB.bin", "50MB.bin", "500MB.bin"]
LABEL_TAM  = {"5MB.bin": "5 MB", "50MB.bin": "50 MB", "500MB.bin": "500 MB"}

PASTA = "graficos"

# --- Estilo dark ---
plt.rcParams.update({
    "figure.facecolor": "#0F172A", "axes.facecolor": "#1E293B",
    "axes.edgecolor": "#475569",   "axes.labelcolor": "#CBD5E1",
    "axes.titlecolor": "#F1F5F9",  "axes.grid": True,
    "grid.color": "#334155",       "grid.linestyle": "--", "grid.linewidth": 0.6,
    "xtick.color": "#94A3B8",      "ytick.color": "#94A3B8",
    "text.color": "#CBD5E1",       "legend.facecolor": "#1E293B",
    "legend.edgecolor": "#475569", "legend.labelcolor": "#CBD5E1",
    "font.size": 11, "axes.titlesize": 13, "figure.dpi": 150,
})

# --- Auxiliares ---
def nome(s): return NOMES.get(s, s)
def cor(s):  return CORES.get(s, "#94A3B8")
def ltam(t): return LABEL_TAM.get(t, t)

def srvs(df):
    p = df["Servidor"].unique()
    return [s for s in ORDEM_SRV if s in p] + [s for s in p if s not in ORDEM_SRV]

def tams(df):
    p = df["Tamanho_Arquivo"].unique()
    return [t for t in ORDEM_TAM if t in p] + [t for t in p if t not in ORDEM_TAM]

def salvar(fig, nome_arq):
    os.makedirs(PASTA, exist_ok=True)
    path = os.path.join(PASTA, nome_arq)
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"  [OK] {path}")
    plt.close(fig)

def legenda(fig, servidores):
    handles = [plt.Rectangle((0,0),1,1, color=cor(s), label=nome(s)) for s in servidores]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02),
               ncol=len(servidores), framealpha=0.15)

# --- Grafico 1: tempo medio por tamanho (painel por qtd de clientes) ---
def g1_tempo_tamanho(df):
    qtds = sorted(df["Qtd_Clientes"].unique())
    ss   = srvs(df); ts = tams(df)
    fig, axes = plt.subplots(1, len(qtds), figsize=(6*len(qtds), 5), sharey=False)
    if len(qtds) == 1: axes = [axes]
    fig.suptitle("Tempo Medio por Arquitetura e Tamanho de Arquivo", fontweight="bold", y=1.02)
    x = np.arange(len(ts)); w = 0.8/len(ss)
    offs = np.linspace(-(len(ss)-1)/2*w, (len(ss)-1)/2*w, len(ss))
    for ax, qtd in zip(axes, qtds):
        sub = df[df["Qtd_Clientes"] == qtd]
        for i, s in enumerate(ss):
            d = sub[sub["Servidor"] == s]
            medios = []; yerr = [[], []]
            for t in ts:
                r = d[d["Tamanho_Arquivo"] == t]
                if len(r):
                    m = float(r["Medio"].iloc[0])
                    medios.append(m)
                    yerr[0].append(m - float(r["Minimo"].iloc[0]))
                    yerr[1].append(float(r["Maximo"].iloc[0]) - m)
                else:
                    medios.append(0); yerr[0].append(0); yerr[1].append(0)
            ax.bar(x+offs[i], medios, w, label=nome(s), color=cor(s), alpha=0.85,
                   yerr=yerr, capsize=4, error_kw={"ecolor":"#94A3B8","linewidth":1.2}, zorder=3)
        ax.set_title(f"{qtd} cliente{'s' if qtd>1 else ''}", fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels([ltam(t) for t in ts])
        ax.set_xlabel("Tamanho"); ax.set_ylabel("Tempo (s)")
    legenda(fig, ss); fig.tight_layout(); salvar(fig, "01_tempo_por_tamanho.png")

# --- Grafico 2: impacto do numero de clientes (linhas) ---
def g2_impacto_clientes(df):
    ss = srvs(df); ts = tams(df)
    fig, axes = plt.subplots(1, len(ts), figsize=(6*len(ts), 5), sharey=False)
    if len(ts) == 1: axes = [axes]
    fig.suptitle("Impacto do Numero de Clientes no Tempo de Download", fontweight="bold", y=1.02)
    for ax, t in zip(axes, ts):
        sub = df[df["Tamanho_Arquivo"] == t]
        for s in ss:
            d = sub[sub["Servidor"] == s].sort_values("Qtd_Clientes")
            if d.empty: continue
            ax.plot(d["Qtd_Clientes"], d["Medio"], marker="o", lw=2.2, ms=7,
                    label=nome(s), color=cor(s), zorder=4)
            ax.fill_between(d["Qtd_Clientes"], d["Minimo"], d["Maximo"],
                            alpha=0.12, color=cor(s))
        ax.set_title(ltam(t), fontweight="bold")
        ax.set_xlabel("Clientes"); ax.set_ylabel("Tempo Medio (s)")
        ax.set_xticks(sorted(df["Qtd_Clientes"].unique()))
    legenda(fig, ss); fig.tight_layout(); salvar(fig, "02_impacto_clientes.png")

# --- Grafico 3: min/med/max no arquivo maior ---
def g3_variabilidade(df):
    ss = srvs(df); qtds = sorted(df["Qtd_Clientes"].unique())
    tam = tams(df)[-1]  # maior arquivo
    fig, axes = plt.subplots(1, len(qtds), figsize=(6*len(qtds), 5), sharey=False)
    if len(qtds) == 1: axes = [axes]
    fig.suptitle(f"Min / Medio / Max por Arquitetura  [{ltam(tam)}]", fontweight="bold", y=1.02)
    x = np.arange(len(ss)); w = 0.25
    for ax, qtd in zip(axes, qtds):
        sub = df[(df["Tamanho_Arquivo"] == tam) & (df["Qtd_Clientes"] == qtd)]
        mins = [float(sub[sub["Servidor"]==s]["Minimo"].iloc[0]) if len(sub[sub["Servidor"]==s]) else 0 for s in ss]
        meds = [float(sub[sub["Servidor"]==s]["Medio"].iloc[0])  if len(sub[sub["Servidor"]==s]) else 0 for s in ss]
        maxs = [float(sub[sub["Servidor"]==s]["Maximo"].iloc[0]) if len(sub[sub["Servidor"]==s]) else 0 for s in ss]
        ax.bar(x-w, mins, w, label="Min",   color="#64748B", alpha=0.85, zorder=3)
        ax.bar(x,   meds, w, label="Medio", color="#3B82F6", alpha=0.85, zorder=3)
        ax.bar(x+w, maxs, w, label="Max",   color="#E05C5C", alpha=0.85, zorder=3)
        ax.set_title(f"{qtd} cliente{'s' if qtd>1 else ''}", fontweight="bold")
        ax.set_xticks(x); ax.set_xticklabels([nome(s) for s in ss], rotation=15, ha="right")
        ax.set_ylabel("Tempo (s)")
    handles = [plt.Rectangle((0,0),1,1, color=c, label=l)
               for c, l in [("#64748B","Min"),("#3B82F6","Medio"),("#E05C5C","Max")]]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5,-0.02), ncol=3, framealpha=0.15)
    fig.tight_layout(); salvar(fig, "03_variabilidade.png")

# --- Grafico 4: heatmap geral ---
def g4_heatmap(df):
    ss = srvs(df); ts = tams(df); qtds = sorted(df["Qtd_Clientes"].unique())
    linhas  = [f"{nome(s)} | {q} cli." for s in ss for q in qtds]
    colunas = [ltam(t) for t in ts]
    M = np.zeros((len(linhas), len(colunas)))
    for i, (s, q) in enumerate((s, q) for s in ss for q in qtds):
        for j, t in enumerate(ts):
            r = df[(df["Servidor"]==s)&(df["Qtd_Clientes"]==q)&(df["Tamanho_Arquivo"]==t)]
            if len(r): M[i,j] = float(r["Medio"].iloc[0])
    fig, ax = plt.subplots(figsize=(max(8, len(colunas)*3), max(6, len(linhas)*0.7)))
    fig.suptitle("Heatmap - Tempo Medio de Download (s)", fontweight="bold")
    im = ax.imshow(M, cmap=plt.colormaps["YlOrRd"], aspect="auto")
    ax.set_xticks(range(len(colunas))); ax.set_xticklabels(colunas)
    ax.set_yticks(range(len(linhas)));  ax.set_yticklabels(linhas, fontsize=9)
    vmax = M.max() or 1
    for i in range(len(linhas)):
        for j in range(len(colunas)):
            ax.text(j, i, f"{M[i,j]:.1f}s", ha="center", va="center",
                    fontsize=9, fontweight="bold",
                    color="white" if M[i,j] > vmax*0.55 else "black")
    fig.colorbar(im, ax=ax, label="Tempo (s)", fraction=0.03, pad=0.02)
    fig.tight_layout(); salvar(fig, "04_heatmap.png")

# --- Dados de demo ---
def demo():
    rows = []
    base = {"5MB.bin": 0.5, "50MB.bin": 4.0, "500MB.bin": 38.0}
    for s in ["servidor_v1.py", "servidor_v2.py"]:
        for t in ["5MB.bin", "50MB.bin", "500MB.bin"]:
            for q in [1, 5, 10, 20]:
                m = base[t] * q if s == "servidor_v1.py" else base[t] * (1 + 0.12*(q-1))
                rows.append({"Servidor":s,"Tamanho_Arquivo":t,"Qtd_Clientes":q,
                              "Minimo":round(m*0.92,3),"Medio":round(m,3),"Maximo":round(m*1.11,3)})
    return pd.DataFrame(rows)

# --- Main ---
def main():
    global PASTA
    p = argparse.ArgumentParser()
    p.add_argument("csv", nargs="?", default="estatisticas_finais.csv")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--saida", default="graficos")
    args = p.parse_args()
    PASTA = args.saida

    print("=" * 50)
    print("  gerar_graficos.py  -  Dev 5")
    print("=" * 50)

    if args.demo:
        print("\n[DEMO] Gerando dados simulados...")
        df = demo()
    else:
        if not os.path.exists(args.csv):
            print(f"[ERRO] Arquivo nao encontrado: '{args.csv}'")
            print("       Use --demo para testar sem CSV real.")
            sys.exit(1)
        print(f"\n[CSV] Lendo '{args.csv}'...")
        df = pd.read_csv(args.csv)

    print(f"  Registros: {len(df)} | Servidores: {df['Servidor'].unique().tolist()}")

    print(f"\n[GRAFICOS] Salvando em '{PASTA}/'...")
    g1_tempo_tamanho(df)
    g2_impacto_clientes(df)
    g3_variabilidade(df)
    g4_heatmap(df)

    print(f"\n[CONCLUIDO] {os.path.abspath(PASTA)}/")
    print("=" * 50)

if __name__ == "__main__":
    main()
