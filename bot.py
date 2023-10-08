from discord.ext import commands
import discord
from cult_fit.cult_api_integration import get_class_details_v2, get_booked_classes, CULT_CENTRES

import os

TOKEN = os.environ.get('DISCORD_BOT_TOKEN')

bot = commands.Bot(command_prefix='!', intents = discord.Intents.all())

@bot.event
async def on_ready():
    print('hit on ready')
    await bot.tree.sync()

@bot.hybrid_group(pass_context=True)
async def cultfit(self, ctx):
    if ctx.invoked_subcommand is None:
        await self.bot.send_cmd_help(ctx)

@cultfit.command(name='cult-classes', help='Get Upcoming Cult Classes')
async def upcoming_cult_classes(context, cult_centre: int=None):

    if cult_centre is None:
        classes = get_class_details_v2()
    else:
        classes = get_class_details_v2(cult_centre)
    booked_classes = get_booked_classes(classes)

    unique_centres = set([c['center_id'] for c in booked_classes])

    centre_text = []

    for centre in unique_centres:
        cult_centres_name = CULT_CENTRES.get(centre, None)
        class_texts = []
        for i in range(len(booked_classes)):
            c = booked_classes[i]
            if c['center_id'] == centre:
                class_texts.append(f"{i}. {c['class_name']} on {c['class_date']} at " + "{0:04.0f}".format(c['class_start_time']) + f" has {c['class_available_seats']} remanining seats")
        
        class_text = '\n'.join(class_texts)
        centre_text.append(f'You have the following classes booked at **{cult_centres_name}**:\n' + class_text)

    message = '\n'.join(centre_text)
    message = message + '\n\nRock it.'
    await context.send(message)

@cultfit.command(name='show-centre-codes', help='Get codes for all centres')
async def show_all_centre_codes(context):
    centre_mapping = list(CULT_CENTRES.items())
    centre_mapping.sort(key=lambda x: x[1])

    info = ''.join([f'{c[0]}    {c[1]}\n' for c in centre_mapping])
    message = f'Please find below the codes for cult centres:\n{info}'

    await context.send(message)


bot.run(TOKEN)