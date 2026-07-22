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

# =============================================================================
# 🎯 SUPER PROMPT - FORMATO HÍBRIDO (Direto + Técnico)
# =============================================================================
PROMPT = """Você é o ROBÔ TRADER CIRÚRGICO, analista técnico de elite.

📚 CONHECIMENTO: Murphy, Elder, Livermore, Elliott Wave, Price Action

📜 REGRA DE OURO: NUNCA OPERE CONTRA A TENDÊNCIA MACRO (4H)

📊 ANÁLISE OBRIGATÓRIA:
1. Tendência 4H: HH/HL (alta) ou LH/LL (baixa)
2. Setup 1H: Pullback em região de valor (EMA, Fib, Suporte/Resistência)
3. Gatilho 15min: Barra Elefante, Martelo, Engolfo com volume
4. Confluência: Mínimo 3 fatores alinhados

✅ SÓ ENTRE SE:
- Tendência 4H clara
- Pullback em região de valor
- Gatilho 15min confirmado
- R/R mínimo 1:2
- Volume confirmando

❌ NUNCA ENTRE SE:
- Mercado lateralizado
- Contra tendência 4H
- Sem gatilho claro
- R/R < 1:2

📝 FORMATO DE SAÍDA OBRIGATÓRIO (use EXATAMENTE este formato):

🚨 ALERTA CIRÚRGICO XAU/USD
💰 Preço Atual: ${current_price:.2f}
⏰ {current_time}

📊 ANÁLISE MULTI-TIMEFRAME:
• Tendência 4H: [ALTA/BAIXA/NEUTRA] ([HH/HL ou LH/LL])
• Setup 1H: [Descrição do pullback/região de valor]
• Gatilho 15min: [Padrão + Volume]

⚖️ CONFLUÊNCIA: [X/6 fatores] [✅/❌]

━━━━━━━━━━━━━━━━━━━━
🎯 DECISÃO: [✅ ENTRADA VALIDADA - COMPRA/VENDA] OU [⛔ AGUARDAR]
━━━━━━━━━━━━━━━━━━━━

[Se ✅ ENTRADA VALIDADA, preencha:]
💰 ENTRADA: $[preço] ([justificativa técnica])
🛑 STOP LOSS: $[preço] ([justificativa - suporte/resistência/EMA])
🎯 TAKE PROFIT: $[preço] ([justificativa - resistência/suporte/projeção])
📊 R/R: 1:[X.X]
💵 APORTE: [X.X]% do capital
🎲 PROBABILIDADE: [X]%

📚 MOTIVO: [Explicação técnica baseada em Murphy/Elder/Livermore/Elliott - cite qual autor/regra fundamentou]

⚠️ GESTÃO:
• Mover stop para breakeven em +1R
• [Outras recomendações de gestão]

[Se ⛔ AGUARDAR, preencha:]
⚠️ MOTIVO DA ESPERA: [Explique o que falta para o setup ser válido]

━━━━━━━━━━━━━━━━━━━━
🔹 Robô Trader Cirúrgico
Baseado em: Murphy, Elder, Livermore, Elliott
━━━━━━━━━━━━━━━━━━━━
"""

def get_market_data():
    """Coleta dados completos dos 3 timeframes com tratamento de erro."""
    try:
        ticker = yf.Ticker("GC=F")
        
        # Tentar obter preço atual
        try:
            current_price_data = ticker.history(period="1d", interval="1m")
            if current_price_data.empty:
                print("⚠️ Aviso: Dados de 1m vazios, tentando 5m...")
                current_price_data = ticker.history(period="1d", interval="5m")
            
            if current_price_data.empty:
                print("❌ Erro: Sem dados de preço disponíveis")
                return None, None, None, None
            
            current_price = float(current_price_data['Close'].iloc[-1])
        except Exception as e:
            print(f"❌ Erro ao obter preço atual: {e}")
            return None, None, None, None
        
        # 4H - Tendência Macro
        df_4h = ticker.history(period="60d", interval="1h").resample('4h').agg({
            'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
        }).dropna().tail(30)
        
        # 1H - Estrutura Intermediária
        df_1h = ticker.history(period="10d", interval="1h").tail(50)
        
        # 15min - Gatilho de Entrada
        df_15m = ticker.history(period="3d", interval="15m").tail(60)
        
        # Verificar se temos dados suficientes
        if df_4h.empty or df_1h.empty or df_15m.empty:
            print("❌ Erro: Dados insuficientes para análise")
            return None, None, None, None
        
        # Identificar tendência 4H
        if len(df_4h) >= 4:
            recent_highs = df_4h['High'].tail(4).values
            recent_lows = df_4h['Low'].tail(4).values
            
            if recent_highs[-1] > recent_highs[-2] and recent_lows[-1] > recent_lows[-2]:
                trend_4h = "ALTA (HH/HL)"
                allowed_direction = "SÓ COMPRA"
            elif recent_highs[-1] < recent_highs[-2] and recent_lows[-1] < recent_lows[-2]:
                trend_4h = "BAIXA (LH/LL)"
                allowed_direction = "SÓ VENDA"
            else:
                trend_4h = "NEUTRA/LATERAL"
                allowed_direction = "AGUARDAR"
        else:
            trend_4h = "INDEFINIDA"
            allowed_direction = "AGUARDAR"
        
        # Calcular EMAs
        ema_20_4h = df_4h['Close'].tail(20).mean()
        ema_50_4h = df_4h['Close'].tail(50).mean() if len(df_4h) >= 50 else None
        
        cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        data = f"""PREÇO ATUAL: ${current_price:.2f}

📈 TENDÊNCIA 4H: {trend_4h}
DIREÇÃO PERMITIDA: {allowed_direction}

EMAs 4H:
- EMA 20: ${ema_20_4h:.2f}
- EMA 50: ${ema_50_4h:.2f} if ema_50_4h else 'N/A'

--- DADOS 4H (Macro - últimos 12 candles) ---
{df_4h[cols].tail(12).to_string(index=False)}

--- DADOS 1H (Setup - últimos 20 candles) ---
{df_1h[cols].tail(20).to_string(index=False)}

--- DADOS 15min (Gatilho - últimos 30 candles) ---
{df_15m[cols].tail(30).to_string(index=False)}"""
        
        return data, current_price, trend_4h, allowed_direction
        
    except Exception as e:
        print(f"❌ Erro crítico em get_market_data: {e}")
        return None, None, None, None

def analyze_with_ai(market_data, current_price):
    """Chama a IA com o super prompt."""
    if market_data is None or current_price is None:
        return "⛔ ERRO: Dados de mercado indisponíveis. Aguardar próxima análise."
    
    current_time = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
    
    # Substituir placeholders
    formatted_prompt = PROMPT.replace("{current_price:.2f}", f"{current_price:.2f}")
    formatted_prompt = formatted_prompt.replace("{current_time}", current_time)
    
    try:
        response = client.chat.completions.create(
            model="qwen/qwen-2.5-7b-instruct",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": f"Analise o mercado de XAU/USD:\n\n{market_data}"}
            ],
            temperature=0.1,
            max_tokens=1200,
            timeout=30
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Erro na IA: {str(e)}"

def send_telegram_alert(message):
    """Envia alerta para o Telegram."""
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    try:
        response = requests.post(
            url,
            json={
                "chat_id": TG_ID,
                "text": message,
                "parse_mode": "Markdown"
            },
            timeout=10
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")
        return False

def run():
    """Função principal de análise."""
    print(f"\n{'='*60}")
    print(f"🤖 ROBÔ TRADER CIRÚRGICO - Análise Iniciada")
    print(f"{'='*60}")
    
    # Coletar dados
    market_data, current_price, trend_4h, allowed_direction = get_market_data()
    
    # Verificar se houve erro na coleta
    if market_data is None or current_price is None:
        print("❌ FALHA CRÍTICA: Não foi possível coletar dados de mercado")
        print("Possíveis causas:")
        print("  1. Mercado fechado (fim de semana/feriado)")
        print("  2. Problema de conexão com Yahoo Finance")
        print("  3. Ticker GC=F indisponível")
        print("\n⏳ Aguardando próxima execução...")
        return
    
    print(f"💰 Preço Atual: ${current_price:.2f}")
    print(f"📈 Tendência 4H: {trend_4h}")
    print(f"🎯 Direção Permitida: {allowed_direction}")
    
    # Analisar com IA
    print("\n🧠 Analisando com IA...")
    analysis = analyze_with_ai(market_data, current_price)
    
    # Imprimir análise completa
    print("\n" + "="*60)
    print(analysis)
    print("="*60)
    
    # Verificar se há setup válido
    if "✅ ENTRADA VALIDADA" in analysis:
        # Montar mensagem para Telegram (já formatada pela IA)
        current_time = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
        
        # Adicionar header com preço atual
        mensagem = f"""🚨 *ALERTA CIRÚRGICO XAU/USD*
💰 *Preço:* ${current_price:.2f}
⏰ {current_time}

{analysis}"""
        
        # Enviar Telegram
        if send_telegram_alert(mensagem):
            print("\n✅ Alerta enviado ao Telegram!")
        else:
            print("\n❌ Falha ao enviar Telegram")
    else:
        print(f"\n⛔ Mercado em espera. Preço: ${current_price:.2f}")
        print("Nenhum alerta enviado (setup não válido)")

if __name__ == "__main__":
    run()
