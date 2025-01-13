import discord
from discord.ext import commands
from discord.ext.commands import BucketType
from discord import app_commands
import asyncio
from collections import defaultdict
import json
from datetime import datetime, timedelta
from collections import defaultdict
from discord.ui import View, Button

TOKEN = 'MTMwNTk2MTI1MzA4ODUyNjM4Ng.GdliL4.I56ecRbipwsPTVh8wS-nj_Xq8-gaezJdVYRkuQ'  # Replace with your actual bot token
LOG_CHANNEL_ID = 1327951728905289809  # Replace with your log channel ID
allowed_ids = [1246156540344406086, 1263778136584097926, 1115964623611506718, 1189832116930879508, 1084066991347871844]
default_prefix = ','
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix=default_prefix, intents=intents, help_command=None)

original_permissions = {}
# Global flag for controlling mass DM
dmall_active = False
user_channels = {}
exempt_roles = set()
whitelisted_users = set()
welcome_channel_id = None
responder_data = {}
verify_role_id = None
punished_users = {}
dmallhrs_active = True
goodbye_channel_id = None
punished_users = set()
USER_ROLES_FILE = 'user_roles.json'
whitelist_settings = {
    'enabled': False,
    'users': []
}
mod_channel_id = None
anti_nuke_settings = {
    'role': {'enabled': False, 'action': None, 'limit': 0},
    'kick': {'enabled': False, 'action': None, 'limit': 0},
    'ban': {'enabled': False, 'action': None, 'limit': 0},
    'addbot': {'enabled': False, 'action': None, 'limit': 0},
    'channel': {'enabled': False, 'action': None, 'limit': 0},
    'webhook_create': {'enabled': False, 'action': None, 'limit': 0},
    'webhook_delete': {'enabled': False, 'action': None, 'limit': 0},
    'ping_everyone': {'enabled': False, 'action': None, 'limit': 0},  # Added protection against @everyone
    'whitelist': {"users": []}
}

role_mapping = {
    'Training': 1327951727965503539,
    'Event': 1327996612877750384,
    'Raids': 1327951727965503540,
    'Useless': 1327951727965503538
}


JAIL_ROLE_NAME = "Jailed"
JAIL_CHANNEL_NAME = "jail"

ping_counts = defaultdict(lambda: defaultdict(int))
ping_counts = defaultdict(int)  # To track pings for users
max_pings = 5  # The threshold for pings

# Function to create an embed
def create_embed(description):
    """Helper function to create an embed with the specified color."""
    embed = discord.Embed(
        description=description,
        color=0x2b2d31
    )
    return embed

# Класс кнопки для ролей
class RoleButton(Button):
    def __init__(self, role_name, role_id):
        super().__init__(label=role_name, style=discord.ButtonStyle.primary)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if role:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"Роль **{role.name}** удалена.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"Роль **{role.name}** добавлена.", ephemeral=True)
        else:
            await interaction.response.send_message("Ошибка: Роль не найдена.", ephemeral=True)


# Команда для отправки изображения и кнопок
@bot.command(name='setpings')
@commands.has_permissions(administrator=True)
async def setpings(ctx, channel_id: int, image_url: str):
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("Неверный ID канала.")
        return

    # Отправка изображения
    await channel.send(image_url)

    # Создание кнопок
    view = View()
    for role_name, role_id in role_mapping.items():
        view.add_item(RoleButton(role_name, role_id))

    await channel.send("click to button for roles:", view=view)
    await ctx.send("done.")


@bot.command()
@commands.has_permissions(administrator=True)  # Ensure only admins can use this command
async def addhrroleall(ctx, role_id: int):
    target_role = ctx.guild.get_role(role_id)  # Role to be assigned
    if not target_role:
        await ctx.send("❌ The specified role ID does not exist.")
        return

    comparison_role = ctx.guild.get_role(1300841052307067009)  # Role ID to compare
    if not comparison_role:
        await ctx.send("❌ Comparison role ID does not exist.")
        return

    added_count = 0  # Counter for tracking how many users received the role
    for member in ctx.guild.members:
        if comparison_role.position < max((r.position for r in member.roles), default=0):  # Check if any of the member's roles are higher
            try:
                if target_role not in member.roles:
                    await member.add_roles(target_role)
                    added_count += 1
            except discord.Forbidden:
                await ctx.send(f"❌ Could not add role to {member.mention} due to insufficient permissions.")
            except Exception as e:
                await ctx.send(f"⚠️ An error occurred while adding role to {member.mention}: {e}")

    await ctx.send(f"✅ Added the role to {added_count} members with roles higher than `{comparison_role.name}`.")

 
@bot.command(name='dmallhrs') 
@commands.has_permissions(administrator=True)
async def dmallhrs(ctx, *, message: str):
    """Отправляет сообщение всем участникам с ролью выше заданной и логирует действия."""
    global dmallhrs_active
    if not dmallhrs_active:
        await ctx.send("Команда `dmallhrs` в настоящее время отключена.")
        return

    target_role_id = 1300841052307067009
    target_role = ctx.guild.get_role(target_role_id)

    if not target_role:
        await ctx.send("Указанная роль не существует.")
        return

    # Используем динамически установленный канал модерации
    mod_channel = bot.get_channel(mod_channel_id) if mod_channel_id else None
    if not mod_channel:
        await ctx.send("Канал модерации не найден. Используйте `,setmodchannel`, чтобы установить его сначала.")
        return

    count = 0

    for member in ctx.guild.members:
        if not dmallhrs_active:  # Проверяем, активна ли команда dmallhrs
            await ctx.send("Команда `dmallhrs` была остановлена.")
            break

        # Пропускаем самого бота и участников, у которых нет ролей выше target_role
        if member.bot or member == ctx.author or not any(role.position > target_role.position for role in member.roles):
            continue

        try:
            await member.send(message)
            count += 1
            await mod_channel.send(f"Сообщение успешно отправлено **{member.display_name}**.")
            await asyncio.sleep(3)  # Задержка в 3 секунды между сообщениями
        except discord.Forbidden:
            # Уведомляем в канал модерации о неудачной отправке
            await mod_channel.send(f"Не удалось отправить сообщение **{member.display_name}** из-за настроек конфиденциальности.")
        except discord.HTTPException as e:
            # Логируем или информируем об ошибках HTTP
            await mod_channel.send(f"Не удалось отправить сообщение **{member.display_name}** (Ошибка: {str(e)})")

    # Итоговое сообщение о количестве отправленных сообщений
    summary_message = f"Сообщение отправлено {count} участникам с ролью выше **{target_role.name}**."
    await mod_channel.send(summary_message)
    await ctx.send(summary_message)

@bot.command(name='mc')
async def member_count(ctx):
    """Displays the member count information."""
    guild = ctx.guild
    total_members = guild.member_count
    human_count = len([member for member in guild.members if not member.bot])
    bot_count = len([member for member in guild.members if member.bot])

    embed = discord.Embed(color=0x2b2d31)  # Dark color for the embed
    embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)
    
    embed.add_field(name="Members", value=str(total_members), inline=True)
    embed.add_field(name="Humans", value=str(human_count), inline=True)
    embed.add_field(name="Bots", value=str(bot_count), inline=True)

    await ctx.send(embed=embed)

@bot.command(name='stopdmhrs')
@commands.has_permissions(administrator=True)
async def stopdmhrs(ctx):
    """Stop the dmallhrs command from sending messages."""
    global dmallhrs_active
    dmallhrs_active = False
    await ctx.send("The `dmallhrs` command has been disabled.")

@bot.command(name='startdmhrs')
@commands.has_permissions(administrator=True)
async def startdmhrs(ctx):
    """Enable the dmallhrs command to send messages again."""
    global dmallhrs_active
    dmallhrs_active = True
    await ctx.send("The `dmallhrs` command has been enabled.")

@bot.command(name='setmodchannel')
@commands.has_permissions(administrator=True)
async def setmodchannel(ctx, channel_id: int):
    """Sets the moderation channel for logging."""
    global mod_channel_id
    mod_channel_id = channel_id
    mod_channel = bot.get_channel(mod_channel_id)
    if mod_channel:
        await ctx.send(f"Канал для логов модерации установлен: {mod_channel.mention}")
    else:
        await ctx.send("Указанный канал не найден. Проверьте ID канала.")

@bot.event
async def on_raw_reaction_remove(payload):
    """Triggered when a reaction is removed from a message via the API."""
    if payload.user_id == bot.user.id:  # Ignore reactions removed by the bot
        return

    channel = bot.get_channel(payload.channel_id)
    if channel is None:
        return  # Channel not found

    message = await channel.fetch_message(payload.message_id)
    emoji = str(payload.emoji)  # Get the emoji that was removed
    user = await channel.guild.fetch_member(payload.user_id)  # Fetch user who removed the reaction

    # Check if mod_channel_id is set
    if mod_channel_id is not None:
        log_channel = bot.get_channel(mod_channel_id)
        if log_channel is not None:
            embed = discord.Embed(
                title="Удалена реакция",
                description=f"{user.mention} удалил реакцию: {emoji}",
                color=discord.Color.red()
            )
            await log_channel.send(embed=embed)

@bot.event
async def on_reaction_remove(reaction, user):
    """Triggered when a reaction is removed from a message."""
    if user.bot:  # Ignore reactions removed by bots
        return

    # Check if mod_channel_id is set
    if mod_channel_id is not None:
        channel = bot.get_channel(mod_channel_id)
        if channel is not None:
            emoji = str(reaction.emoji)  # Get the emoji that was removed
            embed = discord.Embed(
                title="Удалена реакция",
                description=f"{user.mention} удалил реакцию: {emoji}",
                color=discord.Color.red()
            )
            await channel.send(embed=embed)


@bot.command(name='kick')
@commands.has_permissions(kick_members=True)
@commands.cooldown(2, 900, BucketType.user)  # Два использования за 15 минут для одного пользователя
async def kick(ctx, member: discord.Member, *, reason=None):
    """Kick a member from the server."""
    if ctx.author.top_role <= member.top_role:
        # User has equal or lower role compared to the target
        embed = discord.Embed(
            title="Permission Denied",
            description=f"You cannot kick {member.mention} because they have an equal or higher role.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await member.kick(reason=reason)
    embed = discord.Embed(
        title="User has been kicked",
        description=f"{member.mention} has been kicked.",
        color=0x2b2d31
    )
    if reason:
        embed.add_field(name="Reason:", value=reason, inline=False)
    await ctx.send(embed=embed)


@bot.command(name='ban')
@commands.has_permissions(ban_members=True)
@commands.cooldown(2, 900, BucketType.user)  # Два использования за 15 минут для одного пользователя
async def ban(ctx, member: discord.Member, *, reason=None):
    """Ban a member from the server."""
    if ctx.author.top_role <= member.top_role:
        # User has equal or lower role compared to the target
        embed = discord.Embed(
            title="Permission Denied",
            description=f"You cannot ban {member.mention} because they have an equal or higher role.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    await member.ban(reason=reason)
    embed = discord.Embed(
        title="User Banned",
        description=f"{member.mention} has been banned.",
        color=0x2b2d31
    )
    if reason:
        embed.add_field(name="Reason", value=reason, inline=False)
    await ctx.send(embed=embed)

# Обработчик ошибок кулдауна
@kick.error
@ban.error
async def command_cooldown_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        # Сообщение, если команда находится на кулдауне
        embed = discord.Embed(
            title="Command on Cooldown",
            description=f"This command is on cooldown. Try again in {round(error.retry_after)} seconds.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    else:
        raise error

@bot.command(name='unban')
@commands.has_permissions(ban_members=True)
async def unban(ctx, user: str):
    """Unban a member from the server using their username#discriminator or user ID."""
    try:
        # Retrieve the list of banned users
        banned_users = ctx.guild.bans()

        # Check if the input is a user ID
        if user.isdigit():
            user_id = int(user)
            async for ban_entry in banned_users:
                if ban_entry.user.id == user_id:
                    await ctx.guild.unban(ban_entry.user)
                    embed = discord.Embed(
                        title="User Unbanned",
                        description=f"{ban_entry.user.mention} has been unbanned.",
                        color=0x2b2d31
                    )
                    await ctx.send(embed=embed)
                    return
        else:
            # Assume input is username#discriminator
            if '#' not in user:
                raise ValueError("Invalid username format.")

            user_name, user_discriminator = user.split('#')
            async for ban_entry in banned_users:
                if (ban_entry.user.name == user_name and
                        ban_entry.user.discriminator == user_discriminator):
                    await ctx.guild.unban(ban_entry.user)
                    embed = discord.Embed(
                        title="User Unbanned",
                        description=f"{ban_entry.user.mention} has been unbanned.",
                        color=0x2b2d31
                    )
                    await ctx.send(embed=embed)
                    return

        # If no matching user is found
        embed = discord.Embed(
            title="Error",
            description=f"User {user} is not in the ban list.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

    except ValueError:
        # Handle cases where the input format is incorrect
        embed = discord.Embed(
            title="Error",
            description="Please provide a valid username in the format username#1234 or a user ID.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)


@bot.command(name='massunban')
@commands.has_permissions(ban_members=True)
async def mass_unban(ctx, *, users: str):
    """Unban multiple members from the server."""
    banned_users = await ctx.guild.bans()
    user_ids = users.split(',')
    unbanned_count = 0

    for user_id in user_ids:
        user_id = user_id.strip()
        for ban_entry in banned_users:
            if str(ban_entry.user.id) == user_id:
                await ctx.guild.unban(ban_entry.user)
                unbanned_count += 1
                break
        else:
            embed = discord.Embed(
                title="Пользователь не найден",
                description=f"Пользователь с ID {user_id} не найден в бан-листе.",
                color=0x2b2d31
            )
            await ctx.send(embed=embed)

    embed = discord.Embed(
        title="Разбанено пользователей",
        description=f"{unbanned_count} пользователей были разбанены.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='c')
@commands.has_permissions(manage_messages=True)  # Ensure the user has permission to manage messages
async def clear_messages(ctx, amount: int):
    """Удаляет указанное количество сообщений из канала."""
    if amount < 1:
        await ctx.send("Specify that the number of messages to be deleted is greater than zero")
        return

    # Limit the amount to 100 messages at most
    if amount > 100:
        amount = 100

    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"Purged {len(deleted)} messages.", delete_after=5)  # Message will delete after 5 seconds

@bot.command(name='setj2c')
@commands.has_permissions(manage_channels=True)
async def setup_voice_master(ctx):
    """Настраивает систему Voice Master."""
    guild = ctx.guild
    category_name = "Voice Master"
    channel_name = "Join to Create"

    # Создаем категорию, если ее нет
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        category = await guild.create_category(category_name)

    # Создаем голосовой канал, если его нет
    voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
    if voice_channel is None:
        voice_channel = await guild.create_voice_channel(channel_name, category=category)

    await ctx.send(f"✅ Voice Master настроен: категория '{category_name}' и канал '{channel_name}' созданы.")

@bot.event
async def on_voice_state_update(member, before, after):
    """
    Обрабатывает изменения в голосовом состоянии пользователей.
    """
    # Если пользователь зашел в "Join to Create" канал, создаем новый голосовой канал
    if after.channel and after.channel.name == "Join to Create":
        category = after.channel.category  # Категория "Voice Master"
        new_channel = await after.channel.guild.create_voice_channel(
            f"{member.display_name}'s Channel", category=category
        )
        await member.move_to(new_channel)  # Перемещаем пользователя в новый канал

    # Если пользователь покинул голосовой канал
    if before.channel is not None and before.channel != after.channel:
        # Проверяем, является ли канал временным
        if before.channel.name.endswith("'s Channel") and before.channel.category and before.channel.category.name == "Voice Master":
            # Удаляем канал, если он пуст
            if len(before.channel.members) == 0:
                try:
                    await before.channel.delete(reason="Voice Master: Канал пуст")
                except discord.HTTPException as e:
                    print(f"Не удалось удалить канал {before.channel.name}: {e}")


@bot.command(name='setverifyrole')
@commands.has_permissions(administrator=True)
async def set_verify_role(ctx, role_id: int):
    """Sets the role ID to be assigned when using the verifyall command."""
    global verify_role_id
    verify_role_id = role_id
    await ctx.send(embed=create_embed(f"A role with ID {role_id} has been set for verification."))

@bot.command(name='vall')
@commands.has_permissions(administrator=True)
async def verify_all(ctx):
    """Assigns the verification role to all members in the server who do not already have it."""
    if verify_role_id is None:
        await ctx.send(embed=create_embed("First, install the role using the `,setverifyrole` command.")) 
        return

    role = ctx.guild.get_role(verify_role_id)
    if role is None:
        await ctx.send(embed=create_embed("The specified role was not found. Check the role ID.")) 
        return

    # Assign the role to all members who do not already have it
    for member in ctx.guild.members:
        if not member.bot and role not in member.roles:  # Check if the member is not a bot and does not have the role
            await member.add_roles(role)
            await asyncio.sleep(1)  # Delay to prevent hitting rate limits
    
    await ctx.send(embed=create_embed(f"The role `{role.name}` was given to all participants who did not have one."))

@bot.command()
@commands.has_permissions(administrator=True)
async def setjailsys(ctx):
    """Создать систему Jail: текстовый канал и настройки прав."""
    guild = ctx.guild

    # Найти или создать роль "Jailed"
    jail_role = discord.utils.get(guild.roles, name=JAIL_ROLE_NAME)
    if jail_role is None:
        jail_role = await guild.create_role(name=JAIL_ROLE_NAME, reason="Создана роль для системы Jail")
        await ctx.send(f"Роль '{JAIL_ROLE_NAME}' успешно создана.")

    # Создать или найти канал "jail"
    jail_channel = discord.utils.get(guild.channels, name=JAIL_CHANNEL_NAME)
    if jail_channel is None:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),  # Отключить видимость для всех
            jail_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),  # Включить для роли Jailed
        }
        jail_channel = await guild.create_text_channel(
            JAIL_CHANNEL_NAME, overwrites=overwrites, reason="Создан канал для системы Jail"
        )
        await ctx.send(f"Канал '{JAIL_CHANNEL_NAME}' успешно создан.")

    # Удалить права на просмотр каналов для роли "Jailed" во всех других каналах
    for channel in guild.channels:
        if channel != jail_channel:
            await channel.set_permissions(jail_role, view_channel=False)
    
    await ctx.send(
        f"Система Jail настроена. Пользователи с ролью '{JAIL_ROLE_NAME}' теперь могут видеть только канал '{JAIL_CHANNEL_NAME}'."
    )


@bot.command()
@commands.has_permissions(administrator=True)
async def jail(ctx, member: discord.Member, *, reason=None):
    """Добавить пользователя в Jail."""
    guild = ctx.guild

    # Найти роль "Jailed"
    jail_role = discord.utils.get(guild.roles, name=JAIL_ROLE_NAME)
    if jail_role is None:
        await ctx.send(f"Роль '{JAIL_ROLE_NAME}' не найдена. Используйте ,setjailsys для настройки системы.")
        return

    # Сохранить текущие роли пользователя в файл
    try:
        with open(USER_ROLES_FILE, 'r') as f:
            user_roles = json.load(f)
    except FileNotFoundError:
        user_roles = {}

    user_roles[str(member.id)] = [role.id for role in member.roles if role != guild.default_role]

    with open(USER_ROLES_FILE, 'w') as f:
        json.dump(user_roles, f, indent=4)

    # Удалить все роли пользователя и добавить роль "Jailed"
    await member.edit(roles=[jail_role])
    await ctx.send(f"done")


@bot.command()
@commands.has_permissions(administrator=True)
async def unjail(ctx, member: discord.Member):
    """Освободить пользователя из Jail."""
    guild = ctx.guild

    # Найти роль "Jailed"
    jail_role = discord.utils.get(guild.roles, name=JAIL_ROLE_NAME)
    if jail_role is None:
        await ctx.send(f"Роль '{JAIL_ROLE_NAME}' не найдена. Используйте ,setjailsys для настройки системы.")
        return

    # Загрузить роли из файла
    try:
        with open(USER_ROLES_FILE, 'r') as f:
            user_roles = json.load(f)
    except FileNotFoundError:
        user_roles = {}

    roles_to_restore = user_roles.pop(str(member.id), [])
    roles = [guild.get_role(role_id) for role_id in roles_to_restore if guild.get_role(role_id)]

    # Удалить роль "Jailed" и восстановить роли
    await member.edit(roles=roles)
    with open(USER_ROLES_FILE, 'w') as f:
        json.dump(user_roles, f, indent=4)

    await ctx.send(f"{member.mention} unjailed")
# Load anti-nuke settings from JSON file
# Load anti-nuke settings from JSON file
def load_anti_nuke_settings():
    with open('anti_nuke_settings.json', 'r') as file:
        return json.load(file)

# Save anti-nuke settings to JSON file
def save_anti_nuke_settings(data):
    with open('anti_nuke_settings.json', 'w') as file:
        json.dump(data, file, indent=4)

# Load whitelist from JSON file
def load_whitelisted_users():
    try:
        with open('whitelisted_users.json', 'r') as file:
            return set(json.load(file))
    except FileNotFoundError:
        return set()

# Save whitelist to JSON file
def save_whitelisted_users():
    with open('whitelisted_users.json', 'w') as file:
        json.dump(list(whitelisted_users), file, indent=4)

# Send a log message to the moderation channel
async def log_to_mod_channel(message):
    if mod_channel_id is not None:
        log_channel = bot.get_channel(mod_channel_id)
        if log_channel:
            await log_channel.send(message)

# Display anti-nuke configuration
@bot.command(name='antinuke config')
async def antinuke_config(ctx):
    """Displays the current anti-nuke configuration in an embedded message."""
    embed = discord.Embed(
        title="🛡️ Anti-Nuke Configuration",
        description="Current anti-nuke settings:",
        color=discord.Color.blue()
    )

    checkmark = "✅"
    cross = "❌"
    all_actions = ["role", "kick", "ban", "addbot", "channel", "webhook_create", "webhook_delete", "whitelist"]

    for action in all_actions:
        settings = anti_nuke_settings.get(action, {'enabled': False, 'action': 'None', 'limit': 0})
        state = checkmark if settings.get('enabled') else cross
        action_name = action.replace('_', ' ').capitalize()

        if action != "whitelist":
            embed.add_field(
                name=f"{action_name} {state}",
                value=f"**Action**: `{settings.get('action', 'None')}`\n**Limit**: `{settings.get('limit', 0)}`",
                inline=False
            )
        else:
            current_whitelist = ", ".join(f"<@{user_id}>" for user_id in whitelisted_users) if whitelisted_users else "Empty"
            embed.add_field(
                name=f"Whitelist Users {state}",
                value=f"**Users**: {current_whitelist}",
                inline=False
            )

    await ctx.send(embed=embed)

# Command to configure anti-nuke settings
@bot.command(name='antinuke')
async def antinuke(ctx, action: str = None, state: str = None, do: str = None, limit: str = None):
    """Configure anti-nuke settings and manage the whitelist."""
    global anti_nuke_settings

    # Check if the user is an admin (authorized to use this command)
    if ctx.author.id not in allowed_ids:
        await ctx.send("❌ You do not have access to this command. Please contact an authorized user.")
        return

    # Command to configure the anti-nuke settings
    if action == "config":
        await antinuke_config(ctx)
        return

    # Command to manage whitelist
    if action == "whitelist":
        user_input = state
        if user_input.startswith('<@') and user_input.endswith('>'):
            user_id = user_input.strip('<@!>')
        else:
            user_id = user_input

        if not user_id.isdigit():
            await ctx.send("❌ Invalid user ID provided.")
            return

        user_id = int(user_id)

        if user_id not in whitelisted_users:
            whitelisted_users.add(user_id)  # Add to whitelist
            save_whitelisted_users()  # Save whitelist to file
            await ctx.send(f"✅ User ID {user_id} has been added to the whitelist.")
        else:
            await ctx.send(f"❌ User ID {user_id} is already in the whitelist.")
        return

    # Validate action
    valid_actions = ["role", "kick", "ban", "addbot", "channel", "webhook_create", "webhook_delete"]
    if action not in valid_actions:
        await ctx.send(f"❌ Invalid action. Available actions: {', '.join(valid_actions)}.")
        return

    # Validate state (on/off)
    if state not in ["on", "off"]:
        await ctx.send("❌ Invalid state. Use `on` or `off`.")  
        return

    # Set enabled/disabled based on state
    enabled = state.lower() == "on"

    # Parse limit if given
    try:
        limit = int(limit) if limit is not None else 0
    except ValueError:
        await ctx.send("❌ Please enter a valid integer for the limit.")
        return

    # Update anti-nuke settings
    anti_nuke_settings[action] = {
        'enabled': enabled,
        'action': do,
        'limit': limit
    }

    save_anti_nuke_settings(anti_nuke_settings)
    await ctx.send(
        f"✅ Antinuke for `{action}` set to: **{'enabled' if enabled else 'disabled'}**, **action**: `{do}`, **limit**: `{limit}`."
    )

# Helper function to check if the user is whitelisted
def is_whitelisted(user_id):
    return user_id in whitelisted_users

# Initialize settings and whitelist
anti_nuke_settings = load_anti_nuke_settings()
whitelisted_users = load_whitelisted_users()

# Функция для обработки аудита с учетом уже наказанных пользователей
# Обработка действий аудита
async def process_audit_log(guild, action, audit_action, reason):
    async for entry in guild.audit_logs(action=audit_action, limit=1):
        user = entry.user
        if user.bot or is_whitelisted(user.id):
            return

        settings = anti_nuke_settings.get(action, {})
        if settings.get("enabled") and user.id not in punished_users:
            punishment = settings.get("action")
            if punishment == "ban":
                await guild.ban(user, reason=reason)
            elif punishment == "kick":
                await guild.kick(user, reason=reason)

            punished_users.add(user.id)

# Привязка событий
@bot.event
async def on_guild_role_delete(role):
    await process_audit_log(role.guild, 'role', discord.AuditLogAction.role_delete, f"Deleted role {role.name}")

@bot.event
async def on_guild_role_create(role):
    await process_audit_log(role.guild, 'role', discord.AuditLogAction.role_create, f"Created role {role.name}")

@bot.event
async def on_guild_channel_delete(channel):
    await process_audit_log(channel.guild, 'channel', discord.AuditLogAction.channel_delete, f"Deleted channel {channel.name}")

@bot.event
async def on_member_remove(member):
    await process_audit_log(member.guild, 'kick', discord.AuditLogAction.kick, "Kicked a member")

@bot.event
async def on_member_ban(guild, user):
    await process_audit_log(guild, 'ban', discord.AuditLogAction.ban, "Banned a member")

@bot.event
async def on_guild_integrations_update(guild):
    await process_audit_log(guild, 'addbot', discord.AuditLogAction.bot_add, "Added a bot")

@bot.event
async def on_webhooks_update(channel):
    guild = channel.guild
    await process_audit_log(guild, 'webhook_create', discord.AuditLogAction.webhook_create, "Created a webhook")
    await process_audit_log(guild, 'webhook_delete', discord.AuditLogAction.webhook_delete, "Deleted a webhook")

@bot.command(name='setantimention')
@commands.has_permissions(administrator=True)
async def setantimention(ctx, limit: int):
    """Sets the maximum number of allowed mentions before the bot takes action."""
    if limit < 1:
        await ctx.send("❌ Please provide a valid number greater than 0.")
        return

    anti_nuke_settings['mention'] = {
        'enabled': True,
        'limit': limit,
        'action': 'ban'  # Default action; can be modified based on your preference
    }

    save_anti_nuke_settings(anti_nuke_settings)
    await ctx.send(f"✅ Anti-mention protection set to trigger at `{limit}` mentions.")

@bot.event
async def on_message(message):
    if message.author == bot.user or message.author.guild_permissions.administrator:
        return

    # Load mention settings from your anti-nuke configuration
    settings = anti_nuke_settings.get('mention', {})
    if settings.get('enabled') and not is_whitelisted(message.author.id):
        mention_count = len(message.mentions)
        if mention_count >= settings.get('limit', 0):
            # Delete the current channel and create a new one with the same properties
            try:
                old_channel = message.channel
                new_channel = await old_channel.clone(reason="Mention limit exceeded")
                await old_channel.delete(reason="Mention limit exceeded")

                # Send a notification in the newly created channel
                await new_channel.send(f"{message.author.mention} was banned for exceeding the mention limit. This channel has been recreated.")
                
                # Ban the user
                await message.guild.ban(message.author, reason=f"Exceeded mention limit with {mention_count} mentions.")
            except discord.Forbidden:
                await message.channel.send("❌ The bot lacks the necessary permissions to delete or create channels.")
            except discord.HTTPException as e:
                await message.channel.send(f"❌ An error occurred: {e}")

    await bot.process_commands(message)


@bot.command(name='dmall')
@commands.has_permissions(administrator=True)
async def dmall(ctx, *, message: str):
    """Send a DM to all online members on the server."""
    global dmall_active
    dmall_active = True
    log_channel = bot.get_channel(LOG_CHANNEL_ID)

    if log_channel is None:
        await ctx.send(embed=create_embed("Log channel not found."))
        return

    online_members = [member for member in ctx.guild.members if member.status == discord.Status.online and not member.bot]

    success_count = 0
    failure_count = 0

    for member in online_members:
        if not dmall_active:  # Check if we should stop
            await ctx.send(embed=create_embed("Mass DM process stopped."))
            await log_channel.send(embed=create_embed("Mass DM process was interrupted."))
            return

        try:
            await member.send(message)
            success_count += 1
            await log_channel.send(embed=create_embed(f"Message successfully sent to {member.mention}."))
        except discord.Forbidden:
            failure_count += 1
            await log_channel.send(embed=create_embed(f"Could not send message to {member.mention}."))

    await ctx.send(embed=create_embed("Message sent to all online members."))
    await log_channel.send(embed=create_embed(f"dmall summary: {success_count} successful, {failure_count} failed."))

@bot.command(name='dmallstop')
@commands.has_permissions(administrator=True)
async def dmallstop(ctx):
    """Stop the ongoing mass DM process."""
    global dmall_active
    dmall_active = False
    await ctx.send(embed=create_embed("Mass DM process will be stopped."))
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=create_embed("Mass DM process was manually stopped by an administrator."))


@bot.command(name='nuke')
@commands.has_permissions(administrator=True)
async def nuke(ctx, subcommand: str = None, user_id: int = None):
    """Deletes and recreates the channel, or manages whitelist with 'whitelist' subcommand."""
    
    # Check if the author is the owner or in the whitelist
    if ctx.author.id != ctx.guild.owner_id and ctx.author.id not in whitelisted_users:
        await ctx.send(embed=create_embed("You do not have permission to use this command."))
        return

    # Handle whitelist subcommand
    if subcommand == "whitelist":
        if ctx.author.id == ctx.guild.owner_id:
            if user_id:
                whitelisted_users.add(user_id)
                await ctx.send(embed=create_embed(f"User with ID {user_id} has been added to the whitelist."))
            else:
                await ctx.send(embed=create_embed("Please specify a user ID to whitelist."))
        else:
            await ctx.send(embed=create_embed("Only the server owner can manage the whitelist."))
        return

    # If not managing whitelist, proceed with nuke functionality
    # Capture current channel details
    channel = ctx.channel
    channel_position = channel.position
    overwrites = channel.overwrites
    channel_name = channel.name
    channel_topic = channel.topic
    channel_nsfw = channel.is_nsfw()
    channel_slowmode = channel.slowmode_delay
    category = channel.category

    # Delete the channel
    await channel.delete()

    # Recreate the channel with the same settings
    new_channel = await category.create_text_channel(
        name=channel_name,
        topic=channel_topic,
        position=channel_position,
        overwrites=overwrites,
        nsfw=channel_nsfw,
        slowmode_delay=channel_slowmode
    )

    # Inform in the new channel
    await new_channel.send(embed=create_embed("Channel has been recreated!"))

@bot.command(name='responder')
@commands.has_permissions(administrator=True)  # Ensure the user has admin permissions
async def responder(ctx, action: str, *, args: str = ""):
    """Manage responder values (add, get, show, delete)."""
    args_list = [arg.strip() for arg in args.split(',') if arg.strip()]  # Split the arguments

    if action == "add" and len(args_list) == 2:
        name, value = args_list
        # Check if the name already exists
        if name in responder_data:
            await ctx.send(embed=create_embed(f"Responder `{name}` already exists with value `{responder_data[name]}`. Please use a different name."))
        else:
            # Add the name-value pair to the dictionary
            responder_data[name] = value
            await ctx.send(embed=create_embed(f"Responder `{name}` has been added with value `{value}`."))
    elif action == "get" and len(args_list) == 1:
        name = args_list[0]
        # Check if the name exists in the dictionary
        if name in responder_data:
            await ctx.send(embed=create_embed(responder_data[name]))
        else:
            await ctx.send(embed=create_embed(f"No value found for `{name}`."))
    elif action == "show":
        # Show all responders
        if responder_data:
            all_responders = "\n".join([f"`{key}`: `{value}`" for key, value in responder_data.items()])
            await ctx.send(embed=create_embed(f"**All Responders:**\n{all_responders}"))
        else:
            await ctx.send(embed=create_embed("No responders found."))
    elif action == "delete" and len(args_list) == 1:
        name = args_list[0]
        # Check if the name exists in the dictionary
        if name in responder_data:
            del responder_data[name]
            await ctx.send(embed=create_embed(f"Responder `{name}` has been deleted."))
        else:
            await ctx.send(embed=create_embed(f"No responder found with the name `{name}`."))
    else:
        # Invalid usage
        await ctx.send(embed=create_embed("Usage:\n"
                                          "`,responder add (name), (value)` - Add a new responder\n"
                                          "`,responder get (name)` - Get a responder's value\n"
                                          "`,responder show` - Show all responders\n"
                                          "`,responder delete (name)` - Delete a responder"))

@bot.event
async def on_message(message):
    """Respond to messages without the command prefix."""
    if message.author == bot.user:
        return

    # Check if the message is a key in the responder_data dictionary
    if message.content in responder_data:
        await message.channel.send(embed=create_embed(responder_data[message.content]))
    else:
        await bot.process_commands(message)  # Process other commands

@bot.command(name='setprefix')
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, new_prefix: str):
    """Set a new command prefix for the bot."""
    global default_prefix
    default_prefix = new_prefix
    bot.command_prefix = default_prefix  # Update the command prefix
    await ctx.send(embed=discord.Embed(
        title="Prefix Changed",
        description=f"The command prefix has been changed to `{new_prefix}`.",
        color=0x2B2D31
    ))

# Handle missing permissions error globally
@bot.event
async def on_command_error(ctx, error):
    """Handles command errors."""
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing argument! Please provide all required arguments.")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Member not found! Please provide a valid user.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found! Check the available commands with `,help`.")
    else:
        # Log the error and inform the user
        print(f"Unhandled exception: {error}")
        await ctx.send("❌ An error occurred while processing the command.")



@bot.event
async def on_message(message):
    """Respond to messages and commands."""
    if message.author == bot.user:
        return

    # Check if the bot is mentioned
    if bot.user in message.mentions:
        await message.channel.send(f"Yo, my prefix is `{default_prefix}`")

    # Check if the message is a key in the responder_data dictionary
    if message.content in responder_data:
        await message.channel.send(responder_data[message.content])
    else:
        await bot.process_commands(message)  # Process other commands

@bot.command(name='dm')
@commands.has_permissions(administrator=True)
async def dm(ctx, user_id: int, *, message: str):
    """Send a direct message to a user by their ID."""
    log_channel = bot.get_channel(LOG_CHANNEL_ID)  # Замените LOG_CHANNEL_ID на ID вашего лог-канала

    try:
        # Fetch the user by ID
        user = await bot.fetch_user(user_id)

        if user is None:
            await ctx.send(embed=create_embed("User not found."))
            return

        # Send the message to the user
        await user.send(message)

        # Log success message
        await ctx.send(embed=create_embed(f"Message successfully sent to {user.mention}."))

        if log_channel:
            await log_channel.send(embed=create_embed(
                f"📩 **DM Sent**\n"
                f"**From:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                f"**To:** {user.mention} (`{user.id}`)\n"
                f"**Message:** {message}"
            ))

    except discord.Forbidden:
        # Log failure due to permission issue
        await ctx.send(embed=create_embed(f"Could not send message to {user.mention}. They may have DMs disabled."))
        if log_channel:
            await log_channel.send(embed=create_embed(
                f"❌ **DM Failed**\n"
                f"**From:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                f"**To:** {user.mention} (`{user.id}`)\n"
                f"**Reason:** User may have DMs disabled.\n"
                f"**Message:** {message}"
            ))

    except Exception as e:
        # Log any other error
        await ctx.send(embed=create_embed("An error occurred while trying to send the message."))
        if log_channel:
            await log_channel.send(embed=create_embed(
                f"⚠️ **DM Error**\n"
                f"**From:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                f"**To:** <@{user_id}> (`{user_id}`)\n"
                f"**Error:** {str(e)}"
            ))




@bot.command(name='setwelcome')
@commands.has_permissions(administrator=True)
async def set_welcome(ctx, channel: discord.TextChannel):
    """Set the channel where welcome messages will be sent."""
    global welcome_channel_id
    welcome_channel_id = channel.id
    await ctx.send(f"Welcome messages will be sent to {channel.mention}.")

@bot.event
async def on_member_join(member):
    """Send a welcome message when a new member joins."""
    if welcome_channel_id is not None:
        channel = bot.get_channel(welcome_channel_id)
        if channel is not None:
            embed = discord.Embed(
                title="Hello >_<!",
                description=f"{member.mention} has joined **{member.guild.name}**!",
                color=0x2B2D31  # Light blue color
            )
            embed.set_image(url="https://media1.tenor.com/m/swIMdJZK8F0AAAAd/kitten-relaxing-paws.gif")
            await channel.send(embed=embed)

@bot.command()
async def setgoodbye(ctx, channel_id: int):
    """Команда для установки ID канала для прощальных сообщений."""

    global goodbye_channel_id  # Объявляем переменную глобальной
    goodbye_channel_id = channel_id
    await ctx.send(f"The channel for left was successfully set to <#{channel_id}>.")

@bot.event
async def on_member_remove(member):
    """Обрабатываем событие выхода пользователя: сохраняем роли и отправляем прощальное сообщение."""

    # Сохраняем роли пользователя в файл
    user_roles = [role.id for role in member.roles if role.id != member.guild.id]  # исключаем @everyone

    # Загружаем существующие данные из файла, если файл существует
    try:
        with open(USER_ROLES_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    # Проверка, что data — это словарь, если нет, создаем пустой словарь
    if not isinstance(data, dict):
        data = {}

    # Сохраняем роли пользователя в словарь
    data[str(member.id)] = user_roles

    # Сохраняем данные обратно в файл
    with open(USER_ROLES_FILE, 'w') as f:
        json.dump(data, f, indent=4)

    print(f"Роли пользователя {member.name} сохранены.")

    # Отправка прощального сообщения, если канал для этого настроен
    if goodbye_channel_id is not None:
        channel = bot.get_channel(goodbye_channel_id)
        if channel is not None:
            embed = discord.Embed(
                title="Goodbye! 👋",
                description=f"{member.mention} has left **{member.guild.name}**. We'll miss you!",
                color=0x2B2D31 
            )
            embed.set_image(url="https://media1.tenor.com/m/swIMdJZK8F0AAAAd/kitten-relaxing-paws.gif")
            await channel.send(embed=embed)

@bot.command(name="whois")
async def whois(ctx, *, member: discord.Member = None):
    """Get detailed information about a member."""
    member = member or ctx.author  # Default to the author if no member is specified

    embed = discord.Embed(
        title=f"User Info: {member.name}#{member.discriminator}",
        color=member.color,
        timestamp=ctx.message.created_at
    )

    # Safe handling of avatar
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    embed.set_thumbnail(url=avatar_url)

    embed.add_field(name="User ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    # List roles
    roles = [role.mention for role in member.roles if role != ctx.guild.default_role]
    embed.add_field(name=f"Roles ({len(roles)})", value=", ".join(roles) if roles else "None", inline=False)

    embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
    embed.add_field(name="Bot?", value="Yes" if member.bot else "No", inline=True)

    embed.set_footer(text=f"Requested by {ctx.author}", icon_url=(ctx.author.avatar.url if ctx.author.avatar else ctx.author.default_avatar.url))

    await ctx.send(embed=embed)


@bot.command()
async def restore(ctx, user_id: int):
    """Восстанавливаем роли пользователя по ID из файла user_roles.json"""
    try:
        # Загружаем данные о ролях из файла
        with open(USER_ROLES_FILE, 'r') as f:
            data = json.load(f)

        # Проверяем, есть ли роли для указанного пользователя
        if str(user_id) in data:
            roles_to_restore = data[str(user_id)]
            member = ctx.guild.get_member(user_id)

            if member:
                # Восстанавливаем роли для пользователя
                for role_id in roles_to_restore:
                    role = ctx.guild.get_role(role_id)
                    if role:
                        await member.add_roles(role)
                        await ctx.send(f"Роль {role.name} восстановлена для {member.name}")
                    else:
                        await ctx.send(f"Роль с ID {role_id} не найдена.")
            else:
                await ctx.send(f"Пользователь с ID {user_id} не найден на сервере.")
        else:
            await ctx.send(f"Роли для пользователя с ID {user_id} не найдены в базе.")
    
    except FileNotFoundError:
        await ctx.send("Не найден файл с данными о ролях.")
    except Exception as e:
        await ctx.send(f"Произошла ошибка: {str(e)}")


@bot.command(name='permswladd')
@commands.has_permissions(administrator=True)
async def permswladd(ctx, user_id: int):
    """Add a user to the whitelist to allow them to use certain commands."""
    if ctx.guild.owner_id != ctx.author.id:
        await ctx.send("Only the server owner can add users to the whitelist.")
        return

    # Add user ID to the whitelist
    whitelisted_users.add(user_id)
    await ctx.send(f"User <@{user_id}> has been added to the whitelist.")

@bot.command(name='setpermswl')
@commands.has_permissions(administrator=True)
async def setpermswl(ctx, *, role_ids: str):
    """Set roles that should be exempt from permission changes."""
    global exempt_roles
    # Clear existing exempt roles
    exempt_roles.clear()

    # Split the role IDs by comma and add to the set
    invalid_roles = []  # List to track invalid role IDs
    for role_id in role_ids.split(','):
        try:
            role_id_int = int(role_id.strip())
            # Check if the role exists in the guild
            role = ctx.guild.get_role(role_id_int)
            if role:  # Add role ID if it exists
                exempt_roles.add(role_id_int)
            else:  # Track invalid role IDs
                invalid_roles.append(role_id_int)
        except ValueError:
            invalid_roles.append(role_id.strip())  # Track non-numeric IDs

    # Send feedback to the user
    if invalid_roles:
        await ctx.send(f"Invalid role IDs: {', '.join(map(str, invalid_roles))}. Please ensure they're valid and numeric.")
    if exempt_roles:
        await ctx.send(f"Roles with IDs {', '.join(map(str, exempt_roles))} are now exempt from permission changes.")
    else:
        await ctx.send("No valid roles were provided. Please specify valid role IDs.")

@bot.command(name='permsoff')
@commands.has_permissions(administrator=True)
async def permsoff(ctx):
    """Remove certain permissions from roles that have manage roles, manage channels, ban members, kick members, or administrator permissions."""
    if ctx.author.id not in whitelisted_users and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You do not have permission to use this command.")
        return

    guild = ctx.guild
    roles_whitelist = []
    roles_modified = []  # List to track roles that have been modified

    # Get the roles from the command arguments if provided
    if ctx.message.content:
        roles_whitelist = [int(role_id.strip()) for role_id in ctx.message.content.split(',') if role_id.strip().isdigit()]

    for role in guild.roles:
        # Check if the role is exempt or has any of the specified permissions
        if role.id not in exempt_roles and role.id not in roles_whitelist and any([
            role.permissions.manage_roles,
            role.permissions.manage_channels,
            role.permissions.ban_members,
            role.permissions.kick_members,
            role.permissions.administrator
        ]):
            # Store original permissions
            original_permissions[role.id] = role.permissions
            try:
                # Remove all permissions
                await role.edit(permissions=discord.Permissions(0))
                roles_modified.append(role)  # Keep track of modified roles
            except discord.Forbidden:
                await ctx.send(f"Could not modify permissions for {role.name}. The bot does not have permission to modify this role.")
            except discord.HTTPException as e:
                await ctx.send(f"Failed to modify permissions for {role.name}: {e}")

    if roles_modified:
        await ctx.send(f"Manage permissions have been removed from {len(roles_modified)} roles.")
    else:
        await ctx.send("No roles were modified.")

@bot.command(name='permson')
@commands.has_permissions(administrator=True)
async def permson(ctx):
    """Restore manage permissions to roles that were modified by permsoff."""
    if ctx.author.id not in whitelisted_users and ctx.author.id != ctx.guild.owner_id:
        await ctx.send("You do not have permission to use this command.")
        return

    guild = ctx.guild
    roles_restored = 0  # Counter to track restored roles

    for role_id, permissions in original_permissions.items():
        # Get the role from the role ID
        role = guild.get_role(role_id)
        if role:
            try:
                # Restore the original permissions
                await role.edit(permissions=permissions)
                roles_restored += 1
            except discord.Forbidden:
                await ctx.send(f"Could not restore permissions for {role.name}. The bot does not have permission to modify this role.")
            except discord.HTTPException as e:
                await ctx.send(f"Failed to restore permissions for {role.name}: {e}")

    # Clear the original permissions storage after restoring
    original_permissions.clear()

    # Send a message to confirm the action
    await ctx.send(f"Manage and admin permissions have been restored to {roles_restored} roles.")

@bot.command(name='r')
@commands.has_permissions(manage_roles=True)
async def assign_role(ctx, user: str, role_id: int):
    """Assign a role to a user by their username#discriminator or user ID, only if the role is below the issuer's highest role."""
    # Get the role object
    role = ctx.guild.get_role(role_id)

    if role is None:
        await ctx.send(embed=create_embed("Role not found. Please check the role ID."))
        return

    # Attempt to find the member by ID or by username#discriminator
    member = None
    if user.isdigit():  # If the input is a user ID
        member = ctx.guild.get_member(int(user))
    elif '#' in user:  # If the input is username#discriminator
        user_name, user_discriminator = user.split('#')
        for m in ctx.guild.members:
            if m.name == user_name and m.discriminator == user_discriminator:
                member = m
                break
    else:
        await ctx.send(embed=create_embed("Please provide a valid user ID or username in the format `username#1234`."))
        return

    if member is None:
        await ctx.send(embed=create_embed("User not found. Please check the input."))
        return

    # Ensure the role is lower than the highest role of the command issuer
    if role >= ctx.author.top_role:
        await ctx.send(embed=create_embed("You cannot assign a role equal to or higher than your top role."))
        return

    # Assign the role if all checks pass
    try:
        await member.add_roles(role)
        await ctx.send(embed=create_embed(f"Role {role.name} has been assigned to {member.mention}."))
    except discord.Forbidden:
        await ctx.send(embed=create_embed("I don't have permission to assign this role."))
    except discord.HTTPException as e:
        await ctx.send(embed=create_embed(f"Failed to assign role due to an error: {e}"))


@bot.command(name='help')
async def help_command(ctx):
    """Displays a list of available commands grouped by category."""
    help_message = """
    **📚 Available Commands:**

    **🛠 General Commands:**
    
    `,setprefix (new_prefix)` - **Sets a new command prefix for the bot.**
    `,help` - **Displays this help message.**
    `,mc` - **Displays the server member count.**
    

    **🎭 Role Management:**
    
    `,setverifyrole (role_id)` - **Sets the role ID to be assigned during verification.**
    `,vall` - **Assigns the verification role to all members without it.**
    `,r (user) (role_id)` - **Assigns a role to a user by their username#discriminator or user ID (role must be below the issuer's top role).**
    `,setpermswl (role_ids)` - **Sets roles that are exempt from permission changes (comma-separated).**
    `,addhrroleall (role_id)` - **Assigns a specified role to all members who meet a certain condition (e.g., have the 'HR' role).**
    

    **🛡 Anti-Nuke Commands:**
    
    `,antinuke config` - **Displays the current anti-nuke configuration.**
    `,antinuke (action) (state) (do) (limit)` - **Configures anti-nuke settings or manages the whitelist.**
    `,nuke channel` - **Deletes and recreates the current channel.**
    `,nuke whitelist add/remove (user_id)` - **Manages the anti-nuke whitelist.**
    

    **🔨 Moderation Commands:**
    
    `,kick (user_id) [reason]` - **Kicks a user from the server.**
    `,ban (user_id) [reason]` - **Bans a user from the server.**
    `,unban (user_id)` - **Unbans a user from the server.**
    `,massunban (user_id)` - **Unbans multiple users from the server.**
    `,c (count)` - **Deletes the specified number of messages in the current channel.**
    `,setmodchannel (channel_id)` - **Sets the channel for logging moderation actions.**
    

    **💬 Messaging Commands:**
    
    `,dm (user_id) (message)` - **Sends a direct message to a user by their ID.**
    `,dmallhrs (message)` - **Sends a direct message to all members with a role higher than a specified role.**
    `,stopdmhrs` - **Stops the ongoing mass DM process initiated by `,dmallhrs`.**
    `,startdmhrs` - **Enables the `,dmallhrs` command to send messages again.**
    `,dmallstop` - **Stops the ongoing mass DM process.**
    

    **🤖 Responder Commands:**
    
    `,responder add (name), (value)` - **Adds a new responder.**
    `,responder get (name)` - **Retrieves the value of a responder.**
    `,responder show` - **Displays all responders.**
    `,responder delete (name)` - **Deletes a responder.**
    

    **⚙ Server Management:**
    
    `,setj2c` - **Creates a "JOIN TO CREATE" category and voice channel for users.**
    `,setgoodbye (channel_id)` - **Sets the channel for sending goodbye messages when members leave the server.**
    

    **⚡ Permissions & Whitelists:**
   
    `,permswladd (user_id)` - **Adds a user to the permission whitelist.**
    `,setpermswl (role_ids)` - **Sets roles exempt from permission changes.**
    
    **👤 User Commands:**
    
    `,whois (user_id/user)` - **Displays detailed information about a user.**
    `,restore (user_id)` - **Restores the roles of a user to their last known state before leaving the server.**
    """
    await ctx.send(embed=create_embed(help_message))


bot.run(TOKEN)
