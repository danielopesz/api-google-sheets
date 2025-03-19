from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",  # Escopo mais moderno
    "https://www.googleapis.com/auth/drive"
]
SHEET_NAME = "Planilha Agendamento Devolus"

# Autenticação
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
    auth_header = request.headers.get('Authorization', '')
    print(f"🔑 Header de Autorização Recebido: '{auth_header}'")  # Log crítico para debug
    
    expected_token = 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6'
    if auth_header.strip() != expected_token:
        print(f"❌ Falha na Autenticação! Esperado: '{expected_token}' | Recebido: '{auth_header}'")
        return jsonify({"error": "Não autorizado"}), 401

    # Verificação do evento
    data = request.get_json()
    if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
        logger.warning(f"Evento inválido: {data.get('evento') if data else 'Sem dados'}")
        return jsonify({"error": "Evento não suportado"}), 400

    try:
        dados = data['dados']
        logger.debug(f"Dados recebidos: {dados}")
        
        # Mapeamento com tratamento de erros
        nova_linha = [
            dados.get('vistoriador', {}).get('nome', 'Não informado'),  # Coluna A
            str(dados.get('tipoVistoria', {}).get('id', '')),            # Coluna B
            dados.get('locatario', dados.get('locatário', '')),          # Coluna C (ambas formas)
            dados.get('dataHoraInicio', ''),                             # Coluna D
            dados.get('imovel', {}).get('endereco', 'Endereço não encontrado')  # Coluna E
        ]
        
        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos: {nova_linha}")
        
        return jsonify({"message": "Agendamento registrado com sucesso!"}), 201

    except Exception as e:
        logger.error(f"Erro ao processar webhook: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno no processamento"}), 500

@app.route("/")
def home():
    return jsonify({"status": "ativo", "versao": "1.0.1"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)