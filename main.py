import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime
from openai import OpenAI

# Configurações (lidas dos Secrets do GitHub)
API_KEY = os.getenv("OPENROUTER_API_KEY")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_ID = os.getenv("TELEGRAM_CHAT_ID")

client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)

PROMPT = """Você é um Analista Institucional de XAU/USD.
Analise os dados OHLCV fornecidos.
REGRAS:
1. Validação Cruzada: Viés 4H e 1H deve ser confirmado por gatilho 15min.
2. Use Estrutura de Mercado (Topos/Fundos) e Volume.
3. Se não houver confluência clara, DECISÃO deve ser "AGUARDAR".

FORMATO DE SAÍDA OBRIGATÓRIO:
### 📊 RELATÓRIO XAU/USD
**💰 Preço Atual:** [Preço exato no momento da análise]
**🕒 Timestamp:** [Data/Hora]
**📈 Viés 4H/1H:** [Alta/Baixa/Neutro + Motivo]
**🔍 Gatilho 15min:** [Padrão de preço/volume]
**⚖️ Confluência:** [Sim/Não]
** DECISÃO FINAL:** 
- [ ] ✅ ENTRADA VALIDADA
- [ ] ⛔ AGUARDAR
**📝 DETALHES:** (Apenas se ✅)
- Direção: [Compra/Venda]
- Zona: [Preço]
- Invalidação: [Preço]
**⚠️ MOTIVO DA ESPERA:** (Apenas se ⛔)
"""

def run():
    ticker = yf.Ticker("XAUUSD=X")
    
    # Coleta dados dos 3 timeframes
    df_4h = ticker.history(period="10d", interval="1h").resample('4h').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna().tail(12)
    
    df_1h = ticker.history(period="5d", interval="1h").tail(15)
    df_15m = ticker.history(period="2d", interval="15m").tail(20)
    current_price = ticker.history(period="1d", interval="1m")['Close'].iloc[-1]
    
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    data = f"""PREÇO ATUAL: {current_price:.2f}
--- 4H (Macro) ---
{df_4h[cols].to_string(index=False)}
--- 1H (Estrutura) ---
{df_1h[cols].to_string(index=False)}
--- 15min (Gatilho) ---
{df_15m[cols].to_string(index=False)}"""
    
    # Chama o modelo GRATUITO
    response = client.chat.completions.create(
        model="qwen/qwen-2.5-7b-instruct",
        messages=[
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": f"Analise:\n{data}"}
        ],
        temperature=0.1
    )
    
    analysis = response.choices[0].message.content
    print(analysis)
    
    # Envia alerta apenas se houver setup validado
    if "✅ ENTRADA VALIDADA" in analysis:
        mensagem = f""" *ALERTA INSTITUCIONAL XAU/USD*
💰 *Preço Atual:* ${current_price:.2f}
⏰ {datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')}

{analysis}"""
        
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_ID,
                "text": mensagem,
                "parse_mode": "Markdown"
            }
        )
        print(f"✅ Alerta enviado! Preço: ${current_price:.2f}")
    else:
        print(f" Mercado em espera. Preço atual: ${current_price:.2f}")

if __name__ == "__main__":
    run()
