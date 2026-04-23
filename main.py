import discord
from discord import app_commands
from discord.ext import commands, tasks
from playwright.async_api import async_playwright
from PIL import Image
import io, re, datetime, time
from dateutil import parser, tz
import os
import asyncio
from google import genai

client = genai.Client(api_key="GENAI_API_KEY")

# --- SUPPORT SERVERS ---
ServerName = 1234567890

# --- CONFIG ---
TOKEN = 'DISCORD_TOKEN'
SERVER_IDs = [ServerName]
SERVER_NAMES = ["ServerName"]
TARGET_URL = "https://bo2.ggame.jp/en/info/?p=26936"

TZ_OFFSETS = {'PDT': tz.gettz('America/Los_Angeles'), 'CET': tz.gettz('Europe/Berlin')}

HEADER_SEL = "#container > main > div > div > article > div.articleContents > dl:nth-child(1) > dd:nth-child(3)"
EVENT_SELECTORS = [
    "#container > main > div > div > article > div.articleContents > dl:nth-child(1) > dd:nth-child(5)",
    "#container > main > div > div > article > div.articleContents > dl:nth-child(1) > dd:nth-child(6)",
    "#container > main > div > div > article > div.articleContents > dl:nth-child(1) > dd:nth-child(7)"
]


class MatchBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_scheduled_events = True
        intents.members = True
        super().__init__(command_prefix="m.", intents=intents)
        self.guild_reminder_channels = {}

    async def setup_hook(self):
        for guild_id in SERVER_IDs:
            guild_obj = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild_obj)
            await self.tree.sync(guild=guild_obj)

        self.check_events.start()
        print(f"Synced commands to {SERVER_NAMES} and started reminder loop.")

    @tasks.loop(minutes=1)
    async def check_events(self):
        now = datetime.datetime.now(datetime.timezone.utc)

        for guild in self.guilds:
            channel_id = self.guild_reminder_channels.get(guild.id)
            if not channel_id:
                continue

            events = await guild.fetch_scheduled_events()
            for event in events:
                time_until = (event.start_time - now).total_seconds()
                if 1740 <= time_until <= 1800:
                    channel = self.get_channel(channel_id)
                    if channel:
                        interested_list = [u.mention async for u in event.fetch_users(limit=100) if not u.bot]
                        players_str = ", ".join(interested_list) if interested_list else "No one yet!"

                        embed = discord.Embed(title="🕒 Match Starting Soon!", color=0xffcc00)
                        embed.add_field(name="Location", value=event.location or "See Details")
                        embed.add_field(name="Players", value=players_str)
                        await channel.send(content="@everyone", embed=embed)


bot = MatchBot()

#Bot Status
@bot.event
async def on_ready():
    await bot.change_presence(status=discord.Status.dnd,
                              activity=discord.CustomActivity(name="囮役はもちろんオレ以外が行く"))

#Clan Match Event Scheduler
@bot.tree.command(name="cmevent", description="Returns Clan Match schedule and auto-create Discord event")
@app_commands.describe(location="Meeting location", reminder_channel="Channel for 30-min reminder", role="Which role to ping", custom_description="Custom description")
async def matches(interaction: discord.Interaction, location: str, reminder_channel: discord.TextChannel, role: discord.Role, custom_description: str):
    if str(role) != "@everyone":
        role = role.mention
    await interaction.response.defer()
    bot.guild_reminder_channels[interaction.guild_id] = reminder_channel.id

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 3000})
        try:
            await page.goto(TARGET_URL, wait_until="networkidle")
            header_loc = page.locator(HEADER_SEL)
            await header_loc.wait_for(state="attached", timeout=10000)
            header_img = Image.open(io.BytesIO(await header_loc.screenshot()))
            final_images = [header_img]
            target_dt = None

            for selector in EVENT_SELECTORS:
                loc = page.locator(selector)
                try:
                    await loc.wait_for(state="attached", timeout=5000)
                    text = await loc.inner_text()
                    date_match = re.search(r'\[PDT\]\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2})', text)
                    if date_match:
                        match_dt = parser.parse(date_match.group(1)).replace(tzinfo=TZ_OFFSETS['PDT'])
                        if match_dt.timestamp() > time.time():
                            target_dt = match_dt
                            final_images.append(Image.open(io.BytesIO(await loc.screenshot())))
                            break
                except:
                    continue

            await browser.close()

            if len(final_images) < 2:
                await interaction.followup.send("No upcoming matches found.")
                return

            total_h = sum(img.height for img in final_images)
            canvas = Image.new('RGB', (max(img.width for img in final_images), total_h), (255, 255, 255))
            y_offset = 0
            for img in final_images:
                canvas.paste(img, (0, y_offset))
                y_offset += img.height

            with io.BytesIO() as buf:
                canvas.save(buf, 'PNG')
                buf.seek(0)
                status_desc = f"Latest match: <t:{int(target_dt.timestamp())}:F>"
                try:
                    new_event = await interaction.guild.create_scheduled_event(
                        name="Clan Match", start_time=target_dt, end_time=target_dt + datetime.timedelta(hours=2),
                        entity_type=discord.EntityType.external, location=location, description=custom_description, image=buf.getvalue(),
                        privacy_level=discord.PrivacyLevel.guild_only
                    )
                    status_desc += f"\n\n{custom_description}\n\n✅ **Scheduled Event:** {new_event.url}"
                except Exception as e:
                    status_desc += f"\n⚠️ Event error: {e}"
                allowed = discord.AllowedMentions(roles=True)
                await interaction.followup.send(file=discord.File(fp=buf, filename='schedule.png'),
                                                embed=discord.Embed(title="Clan Match Schedule",
                                                                    description=status_desc, color=0x3498db).set_image(
                                                    url="attachment://schedule.png"), content=f"{role}", allowed_mentions=allowed)
        except Exception as e:
            await interaction.followup.send(f"Error: {e}")

#Spiker is an M
@bot.tree.command(name="spiker", description="Deep dark fantasy")
async def spiker(interaction: discord.Interaction):
    embed = discord.Embed(title="SPIKER IS AN M", url="https://www.youtube.com/watch?v=QPQZZqAHJiE",
                          description='"I LOVE BEING AN M" - Spiker', color=discord.Color.blurple())
    embed.set_image(url="https://cdn.discordapp.com/attachments/1487365665949093910/1487645740984565760/Rucz.gif")
    await interaction.response.send_message(embed=embed)

#Spiker is an M Story
spikerprompt = ("Tell me a five paragraph story about how a person literally named Spiker "
          "(his legal name is literally Spiker) became an M (M is ambiguous, try to tell in "
          "a way where M is not explicitly defined. Do not mention any explanation "
          "or background of the name Spiker though. Bold M whenever you use it.")
@bot.tree.command(name="spikerlore", description="Spiker lore")
async def chat(interaction: discord.Interaction):
    await interaction.response.defer()
    responses = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=spikerprompt,
    )

    current_line = ""
    for chunk in responses:
        if chunk.text:
            current_line += chunk.text
            if "\n" in current_line:
                lines = current_line.split("\n")
                for line in lines[:-1]:
                    if line.strip():
                        await interaction.followup.send(line.strip())
                        await asyncio.sleep(5)  # Rate limit safety
                current_line = lines[-1]

    if current_line.strip():
        await interaction.followup.send(current_line.strip())


harryprompt = ("Tell me a five paragraph story about how a person literally named Harry "
          "(his legal name is literally Harry) became gay (Do not mention the names of any partners "
          " and do not mention any explanation "
          "or background of Harry's name. Bold gay whenever you use it.")
@bot.tree.command(name="harrylore", description="Harrylie lore")
async def chat(interaction: discord.Interaction):
    await interaction.response.defer()
    responses = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=harryprompt,
    )

    current_line = ""
    for chunk in responses:
        if chunk.text:
            current_line += chunk.text
            if "\n" in current_line:
                lines = current_line.split("\n")
                for line in lines[:-1]:
                    if line.strip():
                        await interaction.followup.send(line.strip())
                        await asyncio.sleep(5)  # Rate limit safety
                current_line = lines[-1]

    if current_line.strip():
        await interaction.followup.send(current_line.strip())

#Clan Match Schedules
@bot.tree.command(name="cm", description="Shows all upcoming clan matches and highlights the next one")
async def cm(interaction: discord.Interaction):
    await interaction.response.defer()

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={'width': 1280, 'height': 3000})

        try:
            await page.goto(TARGET_URL, wait_until="networkidle")

            # Grab the header image
            header_loc = page.locator(HEADER_SEL)
            await header_loc.wait_for(state="attached", timeout=10000)
            header_img = Image.open(io.BytesIO(await header_loc.screenshot()))

            final_images = [header_img]
            next_event_dt = None
            now_ts = time.time()

            # Iterate through ALL possible event slots
            for selector in EVENT_SELECTORS:
                loc = page.locator(selector)
                if await loc.count() > 0:
                    try:
                        text = await loc.inner_text()
                        # Extract PDT time
                        date_match = re.search(r'\[PDT\]\s*(\d{2}/\d{2}/\d{4}\s*\d{2}:\d{2})', text)

                        if date_match:
                            match_dt = parser.parse(date_match.group(1)).replace(tzinfo=TZ_OFFSETS['PDT'])
                            match_ts = match_dt.timestamp()

                            # Add every found event to the image list
                            final_images.append(Image.open(io.BytesIO(await loc.screenshot())))

                            # Logic: If this match is in the future AND (we haven't found one yet OR it's sooner than the one we found)
                            if match_ts > now_ts:
                                if next_event_dt is None or match_ts < next_event_dt.timestamp():
                                    next_event_dt = match_dt
                    except Exception as e:
                        print(f"Skipping selector {selector}: {e}")
                        continue

            await browser.close()

            if len(final_images) < 2:
                await interaction.followup.send("No clan match data found on the page.")
                return

            # Combine all images (Header + all Event rows)
            total_h = sum(img.height for img in final_images)
            max_w = max(img.width for img in final_images)
            canvas = Image.new('RGB', (max_w, total_h), (255, 255, 255))

            y_offset = 0
            for img in final_images:
                canvas.paste(img, (0, y_offset))
                y_offset += img.height

            with io.BytesIO() as buf:
                canvas.save(buf, 'PNG')
                buf.seek(0)

                desc = "Showing all scheduled matches."
                if next_event_dt:
                    desc = f"**Next Upcoming Match:** <t:{int(next_event_dt.timestamp())}:F> (<t:{int(next_event_dt.timestamp())}:R>)"
                else:
                    desc = "All listed matches have already passed."

                embed = discord.Embed(title="Clan Match Schedule", description=desc, color=0x3498db)
                embed.set_image(url="attachment://schedule.png")

                await interaction.followup.send(
                    file=discord.File(fp=buf, filename='schedule.png'),
                    embed=embed
                )

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}")


bot.run(TOKEN)
