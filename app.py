from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging
from datetime import datetime, timedelta
import pytz  # Adicione esta linha

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
BYPASS_AUTH = os.getenv("BYPASS_AUTH", "true").lower() == "true"

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
        # Converter para UTC e depois para Horário de Brasília (UTC-3)
        dt_utc = datetime.fromisoformat(iso_date.replace('Z', '+00:00')).replace(tzinfo=pytz.utc)
        dt_local = dt_utc.astimezone(pytz.timezone('America/Sao_Paulo'))
        
        # Subtrair 3 horas para corrigir o fuso
        dt_corrigido = dt_local - timedelta(hours=3)
        
        return dt_corrigido.strftime("%d/%m/%Y %H:%M:%S")
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

        # Obter locatário (nomeContato como fallback)
        locatario = dados.get('locatario') or dados.get('nomeContato', 'N/I')

        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'N/I'),  # Coluna A: VISTORIADOR
            locatario,                                        # Coluna B: LOCATÁRIO
            formatar_data(dados.get('dataHoraInicio', '')),   # Coluna C: DATA/HORA
            endereco_completo,                                 # Coluna D: IMÓVEL
            extrair_email(dados.get('observacao', ''))         # Coluna E: E-MAIL
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

# ... (mantenha o restante do código igual)