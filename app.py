from flask import Flask, request, jsonify
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import logging
from datetime import datetime
import pytz
import unicodedata
import re

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

def processar_endereco(imovel):
    try:
        partes = []
        
        # Endereço básico
        if imovel.get('endereco'):
            partes.append(imovel['endereco'])
            
        # Número com vírgula
        if imovel.get('numero'):
            partes.append(f", {imovel['numero']}")
            
        # Complemento
        if imovel.get('complemento'):
            partes.append(f", {imovel['complemento']}")
            
        # Bairro
        if imovel.get('bairro'):
            partes.append(f", {imovel['bairro']}")
            
        # Cidade/UF
        cidade_uf = []
        if imovel.get('cidade'):
            cidade_uf.append(imovel['cidade'])
        if imovel.get('uf'):
            cidade_uf.append(imovel['uf'])
        
        if cidade_uf:
            partes.append(f" - {'-'.join(cidade_uf)}")
        
        # Juntar todas as partes e limpar formatação
        endereco = ''.join(partes).replace(' ,', ',')  # Remove espaços antes de vírgulas
        endereco = re.sub(r'\s+', ' ', endereco)  # Remove múltiplos espaços
        endereco = endereco.strip()
        
        # Padronizar hífen entre bairro e cidade
        endereco = re.sub(r'\s*-\s*', ' - ', endereco)
        
        return endereco
        
    except Exception as e:
        logger.error(f"Erro ao formatar endereço: {str(e)}")
        return "Endereço incompleto"

def processar_observacao(observacao):
    try:
        if not observacao:
            return "N/I", "N/I", "N/I"
            
        partes = [p.strip() for p in observacao.split(',')]
        
        # Determinar tipo
        tipo = "N/I"
        primeira_parte = unicodedata.normalize('NFKD', partes[0].lower())
        if 'entrada' in primeira_parte:
            tipo = "ENTRADA"
        elif 'saida' in primeira_parte or 'saída' in primeira_parte:
            tipo = "SAÍDA"
        
        # Extrair email (segunda parte)
        email = partes[1] if len(partes) > 1 else "N/I"
        
        # Extrair metragem (terceira parte)
        metragem = "N/I"
        if len(partes) > 2:
            numeros = re.findall(r'\d+', partes[2])
            if numeros:
                metragem = numeros[0] + "m²"
        
        return tipo, email, metragem
        
    except Exception as e:
        logger.error(f"Erro ao processar observação: {str(e)}")
        return "N/I", "N/I", "N/I"

@app.route('/api/webhook', methods=['POST'])
def handle_webhook():
    try:
        if BYPASS_AUTH:
            logger.warning("⚠️ MODO INSECURO: Autenticação desativada!")
        
        data = request.get_json()
        if not data or data.get('evento') != 'AGENDAMENTO_NOVO':
            return jsonify({"error": "Evento inválido"}), 400

        dados = data.get('dados', {})
        
        # Processar dados
        imovel = dados.get('imovel', {})
        endereco = processar_endereco(imovel)
        locatario = dados.get('locatario') or dados.get('nomeContato', 'N/I')
        tipo, email, metragem = processar_observacao(dados.get('observacao', ''))

        nova_linha = [
            tipo,                                               # Coluna A: TIPO
            dados.get('vistoriador', {}).get('nome', 'N/I'),    # Coluna B: VISTORIADOR
            locatario,                                          # Coluna C: LOCATÁRIO
            formatar_data(dados.get('dataHoraInicio', '')),     # Coluna D: DATA/HORA
            endereco,                                           # Coluna E: IMÓVEL
            metragem,                                           # Coluna F: METRAGEM
            email                                               # Coluna G: E-MAIL
        ]

        sheet.append_row(nova_linha)
        logger.info(f"Dados inseridos: {nova_linha}")
        
        return jsonify({
            "status": "success",
            "dados_inseridos": {
                "tipo": nova_linha[0],
                "vistoriador": nova_linha[1],
                "locatario": nova_linha[2],
                "data_hora": nova_linha[3],
                "endereco": nova_linha[4],
                "metragem": nova_linha[5],
                "email": nova_linha[6]
            }
        }), 201

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
    return jsonify({"status": "ativo", "versao": "5.0.0"})

@app.route("/api/verificar_novas_entradas", methods=["GET"])
def verificar_novas_entradas():
    try:
        registros = sheet.get_all_records()
        return jsonify({"novas_entradas": registros}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)