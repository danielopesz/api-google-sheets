from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SHEET_NAME = "Planilha Agendamento Devolus"
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "true").lower() == "true"  # Ativar via variável de ambiente

# Autenticação Google Sheets
def get_google_sheet():
    credentials_json = os.getenv("GDRIVE_CREDENTIALS_JSON")
    if not credentials_json:
        raise ValueError("Variável de ambiente GDRIVE_CREDENTIALS_JSON não configurada!")
    
    creds_dict = json.loads(credentials_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    client.timeout = 20
    
    try:
        return client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        logger.error(f"Planilha '{SHEET_NAME}' não encontrada!")
        raise

sheet = get_google_sheet()

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        # Log de diagnóstico
        logger.info("\n=== REQUISIÇÃO RECEBIDA ===")
        logger.info(f"Origem: {request.remote_addr}")
        logger.info(f"User-Agent: {request.headers.get('User-Agent')}")
        logger.info(f"Bypass Auth: {BYPASS_AUTH}")

        # Bypass de autenticação (APENAS PARA AMBIENTE INTERNO)
        if BYPASS_AUTH:
            logger.warning("⚠️ MODO INSECURO: Autenticação via token desativada!")
        else:
            auth_header = request.headers.get('Authorization', '').strip()
            expected_token = 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6'
            if auth_header != expected_token:
                logger.error("Falha de autenticação")
                return jsonify({"error": "Não autorizado"}), 401

        # Validação básica do payload
        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            return jsonify({"error": "Evento inválido"}), 400

        # Processamento dos dados
        dados = data.get('dados', {})
        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'N/I'),
            str(dados.get('tipoVistoria', {}).get('id', '')),
            dados.get('locatario', 'N/I'),
            dados.get('dataHoraInicio', 'N/I'),
            dados.get('imovel', {}).get('endereco', 'N/I')
        ]

        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos: {nova_linha}")

        return jsonify({
            "status": "success",
            "linha_adicionada": nova_linha
        }), 201

    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"error": "Erro interno"}), 500

@app.route("/api/agendamentos", methods=["GET"])
def listar_agendamentos():
    try:
        registros = sheet.get_all_records()
        return jsonify({"total": len(registros), "dados": registros})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return jsonify({
        "status": "ativo",
        "ambiente": "interno" if BYPASS_AUTH else "protegido",
        "aviso": "Autenticação desativada" if BYPASS_AUTH else "Modo seguro"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=BYPASS_AUTH)