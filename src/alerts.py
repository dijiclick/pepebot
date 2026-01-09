"""
Telegram alerts module for sending trade signals.
"""
import os
import asyncio
from datetime import datetime
from typing import Optional, Dict
from telegram import Bot
from telegram.error import TelegramError
from dotenv import load_dotenv

load_dotenv()


class TelegramAlert:
    """Handles Telegram notifications."""

    def __init__(self):
        """Initialize Telegram bot."""
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found")

        self.bot = Bot(token=self.token)

    async def send_message(self, message: str) -> bool:
        """Send a message to Telegram."""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode='HTML'
            )
            return True
        except TelegramError as e:
            print(f"[Telegram] Error sending message: {e}")
            return False

    async def send_high_confidence_alert(
            self,
            direction: str,
            entry: float,
            tp: float,
            sl: float,
            size: float,
            layer_info: str,
            market_status: str,
            adx: float,
            confidence: int,
            reason: str
    ):
        """
        Send alert for high confidence trades (>=80%).
        No X search used.
        """
        emoji = "🟢" if direction == "LONG" else "🔴"
        tp_pct = abs(tp - entry) / entry * 100
        sl_pct = abs(sl - entry) / entry * 100

        message = f"""{emoji} <b>{direction} SIGNAL</b>
1000PEPEUSDT | 10x Isolated

<b>Entry:</b>  {entry:.8f}
<b>TP:</b>     {tp:.8f} (+{tp_pct:.2f}%)
<b>SL:</b>     {sl:.8f} (-{sl_pct:.2f}%)
<b>Size:</b>   ${size:.2f} (0.2% risk)

<b>Layer:</b> {layer_info}
<b>Market:</b> {"🟢" if market_status == "RANGE" else "🟠"} {market_status} (ADX: {adx:.1f})

🤖 <b>Grok Analysis</b>
• Confidence: {confidence}% (technical)
• Reason: {reason}

⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

        await self.send_message(message)

    async def send_borderline_alert(
            self,
            direction: str,
            entry: float,
            tp: float,
            sl: float,
            size: float,
            layer_info: str,
            market_status: str,
            adx: float,
            technical_confidence: int,
            sentiment: str,
            buzz_score: int,
            btc_status: str,
            whale_alert: bool,
            reason: str
    ):
        """
        Send alert for borderline trades (60-79%) confirmed by X search.
        """
        emoji = "🟢" if direction == "LONG" else "🔴"
        tp_pct = abs(tp - entry) / entry * 100
        sl_pct = abs(sl - entry) / entry * 100
        whale_str = "YES" if whale_alert else "NO"

        message = f"""{emoji} <b>{direction} SIGNAL</b> (X Confirmed)
1000PEPEUSDT | 10x Isolated

<b>Entry:</b>  {entry:.8f}
<b>TP:</b>     {tp:.8f} (+{tp_pct:.2f}%)
<b>SL:</b>     {sl:.8f} (-{sl_pct:.2f}%)
<b>Size:</b>   ${size:.2f} (0.2% risk)

<b>Layer:</b> {layer_info}
<b>Market:</b> {"🟢" if market_status == "RANGE" else "🟠"} {market_status} (ADX: {adx:.1f})

🤖 <b>Grok Analysis</b>
• Technical: {technical_confidence}%
• Sentiment: {sentiment} (buzz: {buzz_score})
• BTC: {btc_status}
• Whale Alert: {whale_str}
• Reason: {reason}

⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

        await self.send_message(message)

    async def send_skip_notification(self, reason: str, confidence: int = 0):
        """Send notification when trade is skipped (optional, for debugging)."""
        message = f"""⏭️ <b>SKIP</b>
Confidence: {confidence}%
Reason: {reason}

⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

        await self.send_message(message)

    async def send_startup_message(self):
        """Send message when bot starts."""
        message = """🚀 <b>PEPE Scalping Bot Started</b>

Monitoring: 1000PEPEUSDT
Timeframe: 1m
Leverage: 10x
Max Risk: 0.2% per trade

Bot is now watching for bounce layer setups...

⏱ """ + datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S') + " UTC"

        await self.send_message(message)

    async def send_error_message(self, error: str):
        """Send error notification."""
        message = f"""⚠️ <b>Bot Error</b>

{error}

⏱ {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

        await self.send_message(message)


async def test_telegram():
    """Test Telegram connection."""
    try:
        alert = TelegramAlert()
        await alert.send_message("🧪 Test message from PEPE Scalping Bot")
        print("[Telegram] Test message sent successfully")
    except Exception as e:
        print(f"[Telegram] Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_telegram())
