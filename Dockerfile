FROM python:3.11-slim

# PYTHONUNBUFFERED=1: desativa o buffer de saída do Python.
# Sem isso, os print() e logging do servidor só apareceriam nos logs uando o buffer enchesse.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY utils.py .
COPY servidor_v1.py .
COPY servidor_v2.py .

RUN mkdir -p /app/arquivos


# Como esta imagem serve tanto V1 (9001) quanto V2 (9002) estão expostas ambas.
EXPOSE 9001 9002

CMD ["python", "servidor_v1.py"]
