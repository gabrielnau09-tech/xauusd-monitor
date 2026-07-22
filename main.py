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
# 🎯 SUPER PROMPT - ROBÔ TRADER CIRÚRGICO
# Baseado em: Murphy, Elder, Livermore, Elliott Wave, Price Action
# =============================================================================
PROMPT = """Você é o ROBÔ TRADER CIRÚRGICO, um analista técnico de elite especializado em Day Trade e Swing Trade.

📚 CONHECIMENTO INCORPORADO:
- John Murphy: Análise Técnica clássica, padrões de reversão/continuação, volume
- Alexander Elder: Sistema dos 3 Telões, gestão de risco, psicologia (3M's)
- Jesse Livermore: Pontos Pivô, paciência estratégica, piramidação
- Elliott Wave: Ondas impulsivas (5) e corretivas (3), Fibonacci
- Price Action: Barras Elefante, estrutura de mercado, pullbacks

 REGRA DE OURO (INQUEBRÁVEL):
**NUNCA OPERE CONTRA A TENDÊNCIA MACRO (4H/Diário)**
Esta regra sobrescreve todas as outras. Só opere a favor da tendência dominante.

📊 ANÁLISE OBRIGATÓRIA MULTI-TIMEFRAME:

1️⃣ TENDÊNCIA MACRO (4H/Diário):
   - Identifique: HH/HL (alta) ou LH/LL (baixa)
   - Preço acima/abaixo das médias móveis?
   - Use Teoria de Dow: tendência primária
   - DECISÃO: Só opere NESTA direção

2️ ESTRUTURA INTERMEDIÁRIA (1H):
   - Pullback em região de valor?
   - Suporte/resistência, Fibonacci (38.2%, 50%, 61.8%)
   - EMA 20/50 como suporte dinâmico
   - Osciladores (RSI, MACD) em sobrevenda/sobrecompra?

3️⃣ GATILHO DE ENTRADA (15min):
   - Barra Elefante de Ignição (corpo 70%+, pouco pavio)
   - Padrões: Martelo, Engolfo, Rompimento com volume
   - Volume deve confirmar o movimento
   - Confluência mínima de 3 fatores

⚡ CRITÉRIOS DE ENTRADA CIRÚRGICA:

✅ SÓ ENTRE SE:
1. Tendência 4H clara (HH/HL ou LH/LL)
2. Pullback em região de valor (suporte, Fib, média)
3. Gatilho 15min com barra elefante ou padrão confirmado
4. Volume acima da média no gatilho
5. R/R mínimo 1:2
6. Confluência de 3+ fatores alinhados

❌ NUNCA ENTRE SE:
- Mercado lateralizado/consolidação
- Contra a tendência 4H
- Sem gatilho claro (apenas "achismo")
- R/R menor que 1:2
- Volume fraco/baixo

 FORMATO DE SAÍDA OBRIGATÓRIO:

### 📊 RELATÓRIO XAU/USD - ROBÔ CIRÚRGICO
**💰 Preço Atual:** ${current_price:.2f}
**🕒 Timestamp:** {current_time}

**📈 TENDÊNCIA MACRO (4H):** [Alta/Baixa/Neutra]
- Estrutura: [HH/HL ou LH/LL]
- Posição vs Médias: [Acima/Abaixo]
- **DIREÇÃO PERMITIDA:** [SÓ COMPRA / SÓ VENDA / AGUARDAR]

**🔍 SETUP 1H:**
- Região: [Suporte/Resistência/Fib/EMA]
- Pullback: [Sim/Não]
- Osciladores: [RSI/MACD - condição]

**⚡ GATILHO 15min:**
- Padrão: [Barra Elefante/Martelo/Engolfo/Rompimento]
- Volume: [Alto/Médio/Baixo]
- Confirmação: [Sim/Não]

**⚖️ CONFLUÊNCIA:** [X/6 fatores] ✅/❌
- [ ] Tendência 4H definida
- [ ] Pullback em região de valor
- [ ] Gatilho 15min claro
- [ ] Volume confirmando
- [ ] R/R >= 1:2
- [ ] Alinhamento multi-timeframe

 DECISÃO FINAL:
[✅ ENTRADA VALIDADA - COMPRA]
[✅ ENTRADA VALIDADA - VENDA]
[⛔ AGUARDAR - Sem setup válido]

📝 DETALHES TÉCNICOS (Apenas se ✅):
- Direção: [Compra/Venda]
- Entrada: $[preço]
- Stop Loss: $[preço] (baseado em [suporte/resistência/EMA])
- Take Profit: $[preço] (R/R 1:[X])
- Aporte: [2% máximo do capital]
- Probabilidade: [X]% (baseado em [Murphy/Elder/Livermore])
- Estratégia: [Tendência+Pullback/Rompimento/Reversão]

⚠️ MOTIVO DA ESPERA (Apenas se ⛔):
- [Explique tecnicamente o que falta, ex: "Aguardando pullback até $4080", "Sem confluência - mercado lateralizado", "Gatilho 15min fraco - volume baixo"]

💡 PRINCÍPIO APLICADO:
- [Cite qual autor/regra fundamentou a decisão, ex: "Elder - Sistema Triple Screen", "Livermore - Ponto Pivô", "Murphy - Triângulo Simétrico", "Regra de Ouro - A favor da tendência"]
"""

def get_market_data():
    """Coleta dados completos dos 3 timeframes."""
    ticker = yf.Ticker("GC=F")
    
    # 4H - Tendência Macro
    df_4h = ticker.history(period="60d", interval="1h").resample('4h').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'
    }).dropna().tail(30)
    
    # 1H - Estrutura Intermediária
    df_1h = ticker.history(period="10d", interval="1h").tail(50)
    
    # 15min - Gatilho de Entrada
    df_15m = ticker.history(period="3d", interval="15m").tail(60)
    
    # Preço atual
    current_price = ticker.history(period="1d", interval="1m")['Close'].iloc[-1]
    
    # Identificar tendência 4H
    if len(df_4h) >= 4:
        recent_highs = df_4h['High'].tail(4).values
        recent_lows = df_4h['Low'].tail(4).values
        
        # HH/HL = Alta, LH/LL = Baixa
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
    
    cols = ['Open', 'High', 'Low', 'Close', 'Volume']
    
    data = f"""PREÇO ATUAL: ${current_price:.2f}

📈 TENDÊNCIA 4H: {trend_4h}
DIREÇÃO PERMITIDA: {allowed_direction}

--- DADOS 4H (Macro) ---
{df_4h[cols].tail(12).to_string(index=False)}

--- DADOS 1H (Setup) ---
{df_1h[cols].tail(20).to_string(index=False)}

--- DADOS 15min (Gatilho) ---
{df_15m[cols].tail(30).to_string(index=False)}

MÉDIAS 4H:
- EMA 20: ${df_4h['Close'].tail(20).mean():.2f}
- EMA 50: ${df_4h['Close'].tail(50).mean():.2f} if len(df_4h) >= 50 else 'N/A'

RSI 14 (1H): Calcular baseado nos últimos 14 períodos
MACD (1H): Calcular baseado em EMA 12-26-9"""
    
    return data, current_price, trend_4h, allowed_direction

def analyze_with_ai(market_data, current_price):
    """Chama a IA com o super prompt."""
    # Formatar timestamp
    current_time = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
    
    # Substituir placeholders no prompt
    formatted_prompt = PROMPT.replace("{current_price:.2f}", f"{current_price:.2f}")
    formatted_prompt = formatted_prompt.replace("{current_time}", current_time)
    
    try:
        response = client.chat.completions.create(
            model="qwen/qwen-2.5-7b-instruct",
            messages=[
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": f"Analise o mercado de XAU/USD com base nestes dados:\n\n{market_data}"}
            ],
            temperature=0.1,
            max_tokens=1000
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
        # Montar mensagem para Telegram
        current_time = datetime.utcnow().strftime('%d/%m/%Y %H:%M UTC')
        mensagem = f"""🚨 *ALERTA CIRÚRGICO XAU/USD*
 *Preço:* ${current_price:.2f}
⏰ {current_time}

{analysis}

---
🔹 *Robô Trader Cirúrgico*
Baseado em: Murphy, Elder, Livermore, Elliott"""
        
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
