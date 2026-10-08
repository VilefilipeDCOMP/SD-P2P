# SD-P2P

## P2P

Na pasta `SD-P2P`, gere os arquivos antes de rodar o experimento:

```bash
python gerar_arquivos.py
```

Depois, rode nessa ordem:

```bash
python p2p.py --tracker
python p2p.py --seed arquivos/arquivo_5mb.bin
python p2p.py --peer 1
python p2p.py --peer 2
python p2p.py --peer 3
python p2p.py --peer 4
```

NOTA:
- Cada processo deve rodar em um terminal separado ou ser iniciado pelo benchmark.
- Aguarde o seed cadastrar todos os blocos antes de iniciar os peers.
- Para medir concorrência, inicie os peers próximos um do outro.
- A linha RESULTADO indica conclusão; o peer continua compartilhando.
- Reinicie tracker, seed e peers entre rodadas.
