from discord import SyncWebhook
import os

webhook_url = os.environ.get('INTELLIGENT_INVESTMENT_DISCORD_WEBHOOK_URL')

m = 'Hello My World, Aditya'

webhook = SyncWebhook.from_url(webhook_url)
webhook.send(m)