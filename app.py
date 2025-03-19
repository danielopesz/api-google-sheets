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

# Autenticação Google Sheets
def get_google_sheet():
    credentials_json = os.getenv("GDRIVE_CREDENTIALS_JSON")
    if not credentials_json:
        raise ValueError("Variável de ambiente GDRIVE_CREDENTIALS_JSON não configurada!")
    
    creds_dict = json.loads(credentials_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    client = gspread.authorize(creds)
    
    try:
        return client.open(SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        logger.error(f"Planilha '{SHEET_NAME}' não encontrada!")
        raise

sheet = get_google_sheet()

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        # Log detalhado para debug
        logger.info("\n=== NOVA REQUISIÇÃO RECEBIDA ===")
        logger.info(f"Data/Hora: {datetime.utcnow().isoformat()}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Body (primeiros 500 caracteres): {request.get_data(as_text=True)[:500]}")

        # Verificar User-Agent (obrigatório pela documentação)
        user_agent = request.headers.get('User-Agent')
        if not user_agent or len(user_agent) > 100:
            logger.error("Erro 400 - User-Agent inválido ou ausente")
            return jsonify({"error": "User-Agent inválido"}), 400
        
        # FORÇAR TOKEN MANUALMENTE (APENAS PARA TESTE)
        request.headers['Authorization'] = 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6'
        logger.warning("AUTENTICAÇÃO FORÇADA - REMOVER EM PRODUÇÃO!")

        # Verificação do token (Bearer authentication)
        auth_header = request.headers.get('Authorization', '').strip()
        expected_token = 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6'

        if auth_header != expected_token:
            logger.error(f"TOKEN RECEBIDO: '{auth_header}' | ESPERADO: '{expected_token}'")
            return jsonify({"error": "Não autorizado"}), 401

        # Verificar evento e processar dados
        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            logger.error(f"Erro 400 - Evento inválido: {data.get('evento') if data else 'Sem dados'}")
            return jsonify({"error": "Evento não suportado"}), 400

        # Processamento dos dados
        dados = data.get('dados', {})
        logger.info(f"Dados recebidos: {json.dumps(dados, indent=2)}")
        
        # Mapeamento resiliente com fallbacks
        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'N/I'),  # Coluna A
            str(dados.get('tipoVistoria', {}).get('id', '')),   # Coluna B
            dados.get('locatario', 'N/I'),                      # Coluna C
            dados.get('dataHoraInicio', 'N/I'),                 # Coluna D
            dados.get('imovel', {}).get('endereco', 'N/I')      # Coluna E
        ]

        # Escrever na planilha
        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos com sucesso: {nova_linha}")
        
        return jsonify({"message": "Agendamento registrado com sucesso!"}), 201

    except Exception as e:
        logger.error(f"Erro 500 - {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno no servidor"}), 500

@app.route("/")
def home():
    return jsonify({
        "status": "ativo",
        "versao": "2.0.0",
        "documentacao": "https://api.devolusvistoria.com.br"
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)