import pandas as pd

df = pd.read_csv('resultados_brutos.csv')
df['Tempo_Segundos'] = pd.to_numeric(df['Tempo_Segundos'])

resumo = df.groupby(['Servidor', 'Tamanho_Arquivo', 'Qtd_Clientes'])['Tempo_Segundos'].agg(
    Minimo='min',
    Medio='mean',
    Maximo='max'
).reset_index()

resumo.to_csv('estatisticas_finais.csv', index=False)
print("Analise concluida! Arquivo 'estatisticas_finais.csv' gerado")
print(resumo)
