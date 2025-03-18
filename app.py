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

@app.route('/api/agendamentos', methods=['GET'])
def get_agendamentos():
    try:
        registros = sheet.get_all_records()
        agendamentos = []
        
        for idx, registro in enumerate(registros):
            agendamento = {
                "id": idx,
                "imovel": {
                    "id": 0,
                    "endereco": registro['Imóvel']
                },
                "dataHoraInicio": registro['Data/Hora'],
                "dataHoraFim": registro['Data/Hora'],
                "vistoriador": {
                    "id": 0,
                    "nome": registro['Vistoriador']
                },
                "tipoVistoria": {
                    "id": registro['Tipo']
                },
                "locatario": registro['Locatário'],
                # Campos não mapeados com valores padrão
                "nomeContato": "",
                "telefone": "",
                "observacao": "",
                "empresaFilial": {"id": 0},
                "idVistoriaModelo": 0,
                "idSolicitacaoVistoria": 0
            }
            agendamentos.append(agendamento)
        
        return jsonify(agendamentos)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    # Verificar token de autenticação
    auth_header = request.headers.get('Authorization')
    if auth_header != 'Bearer a991b143-4b65-4027-9b8d-e6a9f7d06bc6':
        return jsonify({"error": "Não autorizado"}), 401

    data = request.json
    if data.get('evento') != 'AGENDAMENTO_NOVO':
        return jsonify({"error": "Evento não suportado"}), 400

    try:
        dados = data['dados']
        # Mapear dados para as colunas da planilha
        nova_linha = [
            dados['vistoriador']['nome'],          # Coluna A - Vistoriador
            dados.get('tipoVistoria', {}).get('id', ''),  # Coluna B - Tipo
            dados.get('locatario', ''),             # Coluna C - Locatário
            dados['dataHoraInicio'],                # Coluna D - Data/Hora
            dados['imovel']['endereco']             # Coluna E - Imóvel
        ]
        sheet.append_row(nova_linha)
        return jsonify({"message": "Agendamento registrado na planilha!"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/teste-conexao", methods=["GET"])
def teste_conexao():
    try:
        # Tentar ler a primeira linha
        valores = sheet.row_values(1)
        return jsonify({"status": "OK", "primeira_linha": valores})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Obtém a porta correta do Render
    app.run(host="0.0.0.0", port=port)
