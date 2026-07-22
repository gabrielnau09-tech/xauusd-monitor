import yfinance as yf
import pandas as pd
import requests
import os
from datetime import datetime, timedelta
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
    """Coleta dados completos dos 3 timeframes com tratamento robusto de erro."""
    try:
        ticker = yf.Ticker("GC=F")
        current_price = None
        
        # Tentar obter preço atual com múltiplas tentativas
        intervals_to_try = ["1m", "5m", "15m", "1h"]
        
        for interval in intervals_to_try:
            try:
                print(f"🔄 Tentando obter preço com intervalo {interval}...")
                data = ticker.history(period="1d", interval=interval)
                
                if not data.empty and 'Close' in data.columns and len(data) > 0:
                    current_price = float(data['Close'].iloc[-1])
                    print(f"✅ Preço obtido com sucesso ({interval}): ${current_price:.2f}")
                    break
            except Exception as e:
                print(f"️ Falha no intervalo {interval}: {e}")
                continue
        
        # Se ainda não conseguiu preço, tentar com período maior
        if current_price is None:
            print("️ Tentando com período de 5 dias...")
            try:
                data = ticker.history(period="5d", interval="1h")
                if not data.empty and 'Close' in data.columns and len(data) > 0:
                    current_price = float(data['Close'].iloc[-1])
                    print(f"✅ Preço obtido com período estendido: ${current_price:.2f}")
            except Exception as e:
                print(f"❌ Falha também com período estendido: {e}")
        
        # Verificação final
        if current_price is None:
            print("❌ ERRO: Não foi possível obter preço de mercado após múltiplas tentativas")
            return None, None, None, None
        
        # Coletar dados dos timeframes
        try:
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
                print("❌ ERRO: Dados insuficientes para análise")
                print(f"  - df_4h: {len(df_4h)} registros")
                print(f"  - df_1h: {len(df_1h)} registros")
                print(f"  - df_15m: {len(df_15m)} registros")
                return None, None, None, None
            
        except Exception as e:
            print(f"❌ Erro ao coletar dados dos timeframes: {e}")
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
        
        # Calcular EMAs com tratamento de erro
        ema_20_4h = df_4h['Close'].tail(20).mean()
        ema_50_4h = df_4h['Close'].tail(50).mean() if len(df_4h) >= 50 else None
        
        # Formatar EMAs corretamente (tratando None)
        ema_20_str = f"${ema_20_4h:.2f}"
        ema_50_str = f"${ema_50_4h:.2f}" if ema_50_4h is not None else "N/A"
        
        cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        
        data = f"""PREÇO ATUAL: ${current_price:.2f}

📈 TENDÊNCIA 4H: {trend_4h}
DIREÇÃO PERMITIDA: {allowed_direction}

EMAs 4H:
- EMA 20: {ema_20_str}
- EMA 50: {ema_50_str}

--- DADOS 4H (Macro - últimos 12 candles) ---
{df_4h[cols].tail(12).to_string(index=False)}

--- DADOS 1H (Setup - últimos 20 candles) ---
{df_1h[cols].tail(20).to_string(index=False)}

--- DADOS 15min (Gatilho - últimos 30 candles) ---
{df_15m[cols].tail(30).to_string(index=False)}"""
        
        return data, current_price, trend_4h, allowed_direction
        
    except Exception as e:
        print(f"❌ Erro crítico em get_market_data: {e}")
        import traceback
        traceback.print_exc()
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
    print(f"⏰ Horário UTC: {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')}")
    
    # Coletar dados
    market_data, current_price, trend_4h, allowed_direction = get_market_data()
    
    # Verificar se houve erro na coleta
    if market_data is None or current_price is None:
        print("\n" + "="*60)
        print("❌ FALHA CRÍTICA: Não foi possível coletar dados de mercado")
        print("="*60)
        print("\nPossíveis causas:")
        print("  1. Mercado fechado (fim de semana/feriado)")
        print("  2. Problema de conexão com Yahoo Finance")
        print("  3. Ticker GC=F indisponível temporariamente")
        print("\n🔧 Soluções:")
        print("  - Aguarde a próxima execução (15 minutos)")
        print("  - Verifique se é dia útil e horário de mercado")
        print("  - O mercado de ouro (GC=F) opera 23h/dia, fecha 1h")
        print("\n⏳ Aguardando próxima execução...")
        return
    
    print(f"\n💰 Preço Atual: ${current_price:.2f}")
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
