from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging
from datetime import datetime
import pytz

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
        dt_utc = datetime.fromisoformat(iso_date.replace('Z', '+00:00')).replace(tzinfo=pytz.utc)
        tz = pytz.timezone('America/Sao_Paulo')
        dt_local = dt_utc.astimezone(tz)
        return dt_local.strftime("%d/%m/%Y %H:%M:%S")
    except Exception as e:
        logger.error(f"Erro ao formatar data: {str(e)}")
        return "Data inválida"

def extrair_email(observacao):
    try:
        return observacao.split(',')[0].strip() if observacao else "N/I"
    except Exception as e:
        logger.error(f"Erro ao extrair email: {str(e)}")
        return "N/I"

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        if BYPASS_AUTH:
            logger.warning("⚠️ MODO INSECURO: Autenticação desativada!")
        
        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            return jsonify({"error": "Evento inválido"}), 400

        dados = data.get('dados', {})

        tipo_vistoria = dados.get('tipoVistoria')
        logger.info(f"Debug tipoVistoria: {'Presente' if tipo_vistoria else 'Ausente'}")
        if tipo_vistoria:
            logger.info(f"Conteúdo tipoVistoria: {json.dumps(tipo_vistoria, indent=2)}")
        
        # Processar dados
        imovel = dados.get('imovel', {})
        endereco = f"{imovel.get('endereco', '')} {imovel.get('numero', '')}, {imovel.get('bairro', '')}, {imovel.get('cidade', '')}-{imovel.get('uf', '')}".strip(' ,')
        locatario = dados.get('locatario') or dados.get('nomeContato', 'N/I')

        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'N/I'),
            locatario,
            formatar_data(dados.get('dataHoraInicio', '')),
            endereco,
            extrair_email(dados.get('observacao', ''))
        ]

        sheet.append_row(nova_linha)
        return jsonify({"status": "success", "dados": nova_linha}), 201

    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"error": "Erro interno"}), 500

@app.route("/api/agendamentos", methods=["GET"])
def listar_agendamentos():
    try:
        return jsonify({"dados": sheet.get_all_records()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return jsonify({"status": "ativo", "versao": "3.1.0"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)