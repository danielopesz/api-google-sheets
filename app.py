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
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "false").lower() == "true"

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

def formatar_data(iso_date):
    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime("%d/%m/%Y %H:%M:%S")
    except Exception as e:
        logger.error(f"Erro ao formatar data: {str(e)}")
        return "Data inválida"

def extrair_email(observacao):
    try:
        if not observacao:
            return "N/I"
        return observacao.split(',')[0].strip()
    except Exception as e:
        logger.error(f"Erro ao extrair email: {str(e)}")
        return "N/I"

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        if BYPASS_AUTH:
            logger.warning("⚠️ MODO INSECURO: Autenticação desativada!")
        else:
            auth_header = request.headers.get('Authorization', '').strip()
            expected_token = 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6'
            if auth_header != expected_token:
                return jsonify({"error": "Não autorizado"}), 401

        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            return jsonify({"error": "Evento inválido"}), 400

        dados = data.get('dados', {})
        
        # Endereço completo
        imovel = dados.get('imovel', {})
        endereco_completo = f"{imovel.get('endereco', '')} {imovel.get('numero', '')}, {imovel.get('bairro', '')}, {imovel.get('cidade', '')}-{imovel.get('uf', '')}".strip(' ,')

        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'N/I'),  # Coluna A: VISTORIADOR
            dados.get('locatario', 'N/I'),                     # Coluna B: LOCATÁRIO
            formatar_data(dados.get('dataHoraInicio', '')),     # Coluna C: DATA/HORA
            endereco_completo,                                  # Coluna D: IMÓVEL
            extrair_email(dados.get('observacao', ''))          # Coluna E: E-MAIL
        ]

        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos: {nova_linha}")

        return jsonify({
            "status": "success",
            "dados_inseridos": {
                "vistoriador": nova_linha[0],
                "locatario": nova_linha[1],
                "data_hora": nova_linha[2],
                "endereco": nova_linha[3],
                "email": nova_linha[4]
            }
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
        "versao": "2.1.0",
        "instrucoes": "Formato esperado: VISTORIADOR | LOCATÁRIO | DATA/HORA | IMÓVEL | E-MAIL"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)