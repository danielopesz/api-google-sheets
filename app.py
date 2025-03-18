from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

app = Flask(__name__)

# Autenticação com Google Sheets usando variável de ambiente
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Carregar credenciais do Google a partir de uma variável de ambiente
credentials_json = os.getenv("GDRIVE_CREDENTIALS_JSON")
if not credentials_json:
    raise ValueError("A variável de ambiente 'GDRIVE_CREDENTIALS_JSON' não foi configurada!")

creds_dict = json.loads(credentials_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Nome da planilha
SHEET_NAME = "Planilha Agendamento Devolus"
sheet = client.open(SHEET_NAME).sheet1

@app.route("/")
def home():
    return jsonify({"message": "API Google Sheets está rodando!"})

@app.route("/dados", methods=["GET"])
def obter_dados():
    """Retorna todos os dados da planilha"""
    dados = sheet.get_all_records()
    return jsonify(dados)

@app.route("/adicionar", methods=["POST"])
def adicionar_dado():
    """Adiciona uma nova linha à planilha"""
    data = request.json
    try:
        sheet.append_row([data["nome"], data["email"], data["idade"]])
        return jsonify({"message": "Dado adicionado com sucesso!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Obtém a porta correta do Render
    app.run(host="0.0.0.0", port=port)
