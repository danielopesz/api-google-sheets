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
EXPECTED_TOKEN = "Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6"

# Autenticação Google Sheets
def get_google_sheet():
    try:
        credentials_json = os.getenv("GDRIVE_CREDENTIALS_JSON")
        if not credentials_json:
            raise ValueError("Variável de ambiente GDRIVE_CREDENTIALS_JSON não configurada!")
        
        creds_dict = json.loads(credentials_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        client.timeout = 20  # Timeout de 20 segundos
        
        return client.open(SHEET_NAME).sheet1
    
    except gspread.SpreadsheetNotFound:
        logger.error(f"Planilha '{SHEET_NAME}' não encontrada!")
        raise
    except Exception as e:
        logger.error(f"Erro na autenticação Google: {str(e)}")
        raise

sheet = get_google_sheet()

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        # Verificação primária de autenticação
        auth_header = request.headers.get('Authorization', '').strip()
        if auth_header != EXPECTED_TOKEN:
            logger.error(f"Autenticação falhou. Recebido: '{auth_header}'")
            return jsonify({"error": "Não autorizado"}), 401

        # Verificação secundária do User-Agent
        user_agent = request.headers.get('User-Agent')
        if not user_agent or len(user_agent) > 100:
            logger.error("User-Agent inválido ou ausente")
            return jsonify({"error": "User-Agent inválido"}), 400

        # Log de diagnóstico seguro
        logger.info("\n=== REQUISIÇÃO VÁLIDA RECEBIDA ===")
        logger.info(f"Data/Hora: {datetime.utcnow().isoformat()}")
        logger.info(f"IP Origem: {request.remote_addr}")
        logger.info(f"User-Agent: {user_agent}")

        # Processamento do payload
        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            logger.error("Evento não suportado ou formato inválido")
            return jsonify({"error": "Evento não suportado"}), 400

        dados = data.get('dados', {})
        
        # Validação de campos obrigatórios
        required_fields = {
            'vistoriador': ['nome'],
            'imovel': ['endereco'],
            'dataHoraInicio': None
        }
        
        for field, subfields in required_fields.items():
            if not dados.get(field):
                logger.error(f"Campo obrigatório faltando: {field}")
                return jsonify({"error": f"Campo '{field}' é obrigatório"}), 400
                
            if subfields:
                for subfield in subfields:
                    if not dados[field].get(subfield):
                        logger.error(f"Subcampo obrigatório faltando: {field}.{subfield}")
                        return jsonify({"error": f"Campo '{field}.{subfield}' é obrigatório"}), 400

        # Construção da linha para planilha
        nova_linha = [
            dados['vistoriador']['nome'],               # Coluna A
            str(dados.get('tipoVistoria', {}).get('id', '')),  # Coluna B
            dados.get('locatario', ''),                 # Coluna C
            dados['dataHoraInicio'],                    # Coluna D
            dados['imovel']['endereco']                 # Coluna E
        ]

        # Escrita na planilha
        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos: {nova_linha}")

        return jsonify({
            "status": "sucesso",
            "mensagem": "Agendamento registrado",
            "id_planilha": sheet.spreadsheet.id
        }), 201

    except Exception as e:
        logger.error(f"Erro interno: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno no processamento"}), 500

@app.route("/")
def home():
    return jsonify({
        "status": "ativo",
        "versao": "3.0.0",
        "documentacao": "https://api.devolusvistoria.com.br"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)