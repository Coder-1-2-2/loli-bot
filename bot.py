import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import time
import random
from io import BytesIO
import asyncio
from typing import Optional
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not TOKEN:
    raise ValueError("❌ ERROR: No se encontró el token en las variables de entorno. "
                     "Por favor, configura DISCORD_BOT_TOKEN.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

LOLICON_API = "https://api.lolicon.app/setu/v2"

# Almacenamiento de sesiones activas
active_sessions = {}
SESSION_TIMEOUT = 1800  # 30 minutos

# Enlaces de donación
KOFI_URL = "https://ko-fi.com/coder122"
KOFI_BUTTON = "https://storage.ko-fi.com/cdn/kofi6.png?v=6"
KOFI_EMBED = "https://storage.ko-fi.com/cdn/kofi1.png"

class SessionManager:
    @staticmethod
    def create_session(images_data, user_id):
        session_id = f"{user_id}_{int(time.time())}"
        session = {
            'id': session_id,
            'images': images_data,
            'created_at': time.time(),
            'last_accessed': time.time(),
            'expires_at': time.time() + SESSION_TIMEOUT
        }
        active_sessions[session_id] = session
        return session_id
    
    @staticmethod
    def get_session(session_id):
        if session_id in active_sessions:
            session = active_sessions[session_id]
            if time.time() > session['expires_at']:
                del active_sessions[session_id]
                return None
            
            session['last_accessed'] = time.time()
            session['expires_at'] = time.time() + SESSION_TIMEOUT
            return session
        return None
    
    @staticmethod
    def cleanup_expired_sessions():
        current_time = time.time()
        expired = [sid for sid, sess in active_sessions.items() 
                  if current_time > sess['expires_at']]
        for sid in expired:
            del active_sessions[sid]

class DonateView(discord.ui.View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
        self.add_item(discord.ui.Button(
            label="☕ Donar en Ko-fi",
            style=discord.ButtonStyle.link,
            url=KOFI_URL,
            emoji="❤️"
        ))
        self.add_item(discord.ui.Button(
            label="⭐ Github",
            style=discord.ButtonStyle.link,
            url="https://github.com",
            emoji="⭐"
        ))

class LoliconSearchView(discord.ui.View):
    def __init__(self, images_data, current_index=0, session_id=None, timeout=1800):
        super().__init__(timeout=timeout)
        self.images_data = images_data
        self.current_index = current_index
        self.total_images = len(images_data)
        self.session_id = session_id
        
        self.pixiv_button = discord.ui.Button(
            label="🔗 Pixiv",
            style=discord.ButtonStyle.link,
            url=f"https://www.pixiv.net/artworks/{images_data[current_index]['pid']}",
            row=0
        )
        self.add_item(self.pixiv_button)
        self.update_buttons()
        
    def update_buttons(self):
        for child in self.children:
            if hasattr(child, 'label'):
                if child.label == "⬅️ Anterior":
                    child.disabled = self.current_index == 0
                elif child.label == "Siguiente ➡️":
                    child.disabled = self.current_index == self.total_images - 1
                elif child.label.startswith(tuple('1234567890/')):
                    child.label = f"{self.current_index + 1}/{self.total_images}"
        
        self.pixiv_button.url = f"https://www.pixiv.net/artworks/{self.images_data[self.current_index]['pid']}"
    
    async def create_embed(self):
        img = self.images_data[self.current_index]
        
        embed = discord.Embed(
            title=img['title'][:256],
            color=discord.Color.random(),
            url=f"https://www.pixiv.net/artworks/{img['pid']}"
        )
        
        embed.set_image(url=img['url'])
        embed.add_field(name="🎨 Artista", value=img['author'], inline=True)
        embed.add_field(name="🔢 PID", value=str(img['pid']), inline=True)
        
        info_text = f"**R18:** {'✅' if img['r18'] else '❌'}\n"
        info_text += f"**AI:** {'✅' if img.get('aiType', 0) == 1 else '❌'}\n"
        info_text += f"**Ancho:** {img['width']}\n"
        info_text += f"**Alto:** {img['height']}"
        
        embed.add_field(name="ℹ️ Información", value=info_text, inline=False)
        
        if img['tags']:
            tags_text = ', '.join(img['tags'][:5])
            if len(img['tags']) > 5:
                tags_text += f" (+{len(img['tags']) - 5})"
            embed.add_field(name="🏷️ Tags", value=tags_text[:1024], inline=False)
        
        if self.session_id:
            session_info = f"**Sesión ID:** `{self.session_id[:8]}...`\n"
            session_info += f"**Expira:** <t:{int(time.time() + SESSION_TIMEOUT)}:R>"
            embed.add_field(name="💾 Sesión", value=session_info, inline=False)
        
        # Añadir recordatorio de donación (aleatorio, 20% de probabilidad)
        if random.random() < 0.2:
            embed.set_footer(text=f"❤️ ¿Te gusta el bot? Considera donar con /donate • {time.strftime('%H:%M:%S')}")
        else:
            embed.set_footer(text=f"Proporcionado por Lolicon API • {time.strftime('%H:%M:%S')}")
        
        return embed
    
    @discord.ui.button(label="⬅️ Anterior", style=discord.ButtonStyle.secondary, row=0)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_index -= 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.gray, row=0)
    async def counter(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
    
    @discord.ui.button(label="Siguiente ➡️", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_index += 1
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="🖼️ Ver HD", style=discord.ButtonStyle.primary, row=1)
    async def hd_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        img = self.images_data[self.current_index]
        
        try:
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.pixiv.net/'}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(img['url'], headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.read()
                        file = discord.File(BytesIO(data), filename=f"pixiv_{img['pid']}.jpg")
                        await interaction.followup.send(
                            content=f"**{img['title'][:100]}**\nArtista: {img['author']} | PID: {img['pid']}",
                            file=file,
                            ephemeral=True
                        )
                    else:
                        await interaction.followup.send("❌ No se pudo obtener la imagen HD", ephemeral=True)
                        
        except Exception:
            await interaction.followup.send("❌ Error al obtener la imagen HD", ephemeral=True)
    
    @discord.ui.button(label="📋 Enviar Todas", style=discord.ButtonStyle.success, row=1)
    async def send_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Intentar crear DM
            try:
                dm_channel = await interaction.user.create_dm()
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ No puedo enviarte mensajes privados. Por favor, habilita los DMs.",
                    ephemeral=True
                )
                return
            
            await interaction.followup.send(
                f"📤 Enviando {len(self.images_data)} imágenes por DM...",
                ephemeral=True
            )
            
            # Enviar mensaje inicial en DM
            await dm_channel.send(
                f"📚 **Búsqueda completa - {len(self.images_data)} imágenes**\n"
                f"Sesión ID: `{self.session_id}`\n"
                f"Enviando imágenes..."
            )
            
            # Enviar todas las imágenes
            sent_urls = []
            pixiv_links = []
            
            for i, img in enumerate(self.images_data, 1):
                try:
                    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.pixiv.net/'}
                    
                    async with aiohttp.ClientSession() as session:
                        async with session.get(img['url'], headers=headers, timeout=30) as response:
                            if response.status == 200:
                                data = await response.read()
                                file = discord.File(
                                    BytesIO(data), 
                                    filename=f"pixiv_{img['pid']}.jpg"
                                )
                                await dm_channel.send(file=file)
                            else:
                                sent_urls.append(f"{i}. {img['url']}")
                                await dm_channel.send(img['url'])
                    
                    pixiv_links.append(f"{i}. https://www.pixiv.net/artworks/{img['pid']}")
                    
                    await asyncio.sleep(0.5)
                    
                except Exception:
                    sent_urls.append(f"{i}. {img['url']}")
                    await dm_channel.send(img['url'])
                    pixiv_links.append(f"{i}. https://www.pixiv.net/artworks/{img['pid']}")
                    await asyncio.sleep(0.5)
                    continue
            
            # Enviar enlaces Pixiv al final
            if pixiv_links:
                links_text = "**Enlaces Pixiv:**\n" + "\n".join(pixiv_links[:50])
                if len(pixiv_links) > 50:
                    links_text += f"\n\n... y {len(pixiv_links) - 50} más"
                
                await dm_channel.send(links_text)
            
            # Enviar URLs proxy si hay
            if sent_urls:
                urls_text = "**URLs proxy:**\n" + "\n".join(sent_urls[:20])
                if len(sent_urls) > 20:
                    urls_text += f"\n\n... y {len(sent_urls) - 20} más"
                await dm_channel.send(urls_text)
            
            # Añadir mensaje de donación en DM
            donate_embed = discord.Embed(
                title="❤️ ¡Gracias por usar el bot!",
                description="Si disfrutas usando este bot, considera apoyar su desarrollo con una donación.",
                color=discord.Color.gold()
            )
            donate_embed.set_thumbnail(url=KOFI_EMBED)
            donate_embed.add_field(
                name="☕ Ko-fi",
                value=f"[Haz clic aquí para donar]({KOFI_URL})",
                inline=False
            )
            donate_embed.set_footer(text="¡Cada donación ayuda a mantener el bot funcionando!")
            
            await dm_channel.send(embed=donate_embed)
            await dm_channel.send(f"✅ **Total:** {len(self.images_data)} imágenes enviadas")
            
            await interaction.followup.send(
                f"✅ ¡Listo! Te he enviado {len(self.images_data)} imágenes por DM.",
                ephemeral=True
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
    
    @discord.ui.button(label="💾 Guardar", style=discord.ButtonStyle.blurple, row=1)
    async def save_session_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        if not self.session_id:
            await interaction.followup.send("❌ No hay sesión activa para guardar", ephemeral=True)
            return
        
        try:
            session_data = {
                'session_id': self.session_id,
                'created_at': time.time(),
                'expires_at': time.time() + SESSION_TIMEOUT,
                'total_images': len(self.images_data),
                'images': self.images_data
            }
            
            filename = f"session_{self.session_id}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)
            
            file = discord.File(filename, filename=f"sesion_{self.session_id}.json")
            
            embed = discord.Embed(
                title="✅ Sesión Guardada",
                description=f"**Sesión ID:** `{self.session_id}`\n"
                           f"**Imágenes:** {len(self.images_data)}\n"
                           f"**Expira:** <t:{int(time.time() + SESSION_TIMEOUT)}:R>\n\n"
                           f"Usa `/loli_restore` con este archivo para restaurar la sesión.",
                color=discord.Color.green()
            )
            
            await interaction.followup.send(embed=embed, file=file, ephemeral=True)
            
            if os.path.exists(filename):
                os.remove(filename)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error al guardar: {str(e)}", ephemeral=True)

class SearchModal(discord.ui.Modal, title="🔍 Búsqueda Avanzada"):
    def __init__(self, is_dm=False):
        super().__init__(timeout=300)
        self.is_dm = is_dm
        
        self.tags_input = discord.ui.TextInput(
            label="Tags (separados por comas)",
            placeholder="ej: genshin, blue_archive",
            required=False,
            max_length=200,
            style=discord.TextStyle.short
        )
        
        self.uid_input = discord.ui.TextInput(
            label="UIDs de Artistas (separados por comas)",
            placeholder="ej: 123456, 789012",
            required=False,
            max_length=100,
            style=discord.TextStyle.short
        )
        
        if is_dm:
            r18_placeholder = "0=Safe, 1=R18, 2=Ambos (en DMs todo está permitido)"
        else:
            r18_placeholder = "0=Safe, 1=R18 (solo canales NSFW), 2=Ambos"
            
        self.r18_input = discord.ui.TextInput(
            label="R18 (0=Safe, 1=R18, 2=Ambos)",
            placeholder=r18_placeholder,
            default="0",
            required=False,
            max_length=1,
            style=discord.TextStyle.short
        )
        
        self.num_input = discord.ui.TextInput(
            label="Número de imágenes (1-20)",
            placeholder="10",
            default="10",
            required=False,
            max_length=2,
            style=discord.TextStyle.short
        )
        
        self.add_item(self.tags_input)
        self.add_item(self.uid_input)
        self.add_item(self.r18_input)
        self.add_item(self.num_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        try:
            r18_value_str = self.r18_input.value.strip()
            if not r18_value_str:
                r18_value = 0
            else:
                try:
                    r18_value = int(r18_value_str)
                    if r18_value not in [0, 1, 2]:
                        r18_value = 0
                except ValueError:
                    r18_value = 0
            
            if r18_value == 1 and not self.is_dm and not interaction.channel.nsfw:
                await interaction.followup.send(
                    "❌ Las imágenes R18 solo pueden buscarse en canales NSFW",
                    ephemeral=True
                )
                return
            
            params = {
                'r18': r18_value,
                'num': min(int(self.num_input.value) if self.num_input.value.strip().isdigit() else 10, 20),
                'size': ['original'],
                'proxy': 'i.yuki.sh',
            }
            
            if self.tags_input.value.strip():
                tags = [t.strip() for t in self.tags_input.value.split(',') if t.strip()]
                if tags:
                    params['tag'] = tags
            
            if self.uid_input.value.strip():
                uids = [uid.strip() for uid in self.uid_input.value.split(',') if uid.strip()]
                if uids:
                    params['uid'] = uids
            
            data = await fetch_lolicon_data(params)
            
            if not data or not data.get('data'):
                await interaction.followup.send("❌ No se encontraron resultados", ephemeral=True)
                return
            
            images_data = []
            for img in data['data']:
                image_info = {
                    'title': img['title'],
                    'author': img['author'],
                    'pid': img['pid'],
                    'url': img['urls']['original'],
                    'r18': img['r18'],
                    'width': img['width'],
                    'height': img['height'],
                    'tags': img['tags'],
                    'aiType': img.get('aiType', 0)
                }
                images_data.append(image_info)
            
            session_id = SessionManager.create_session(images_data, interaction.user.id)
            
            view = LoliconSearchView(images_data, session_id=session_id)
            embed = await view.create_embed()
            
            await interaction.followup.send(embed=embed, view=view)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

async def fetch_lolicon_data(params):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                LOLICON_API,
                json=params,
                headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'},
                timeout=30
            ) as response:
                return await response.json() if response.status == 200 else None
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return None

async def search_and_send_images(interaction, params, is_dm=False):
    if interaction.response.is_done():
        msg = await interaction.followup.send("🔍 Buscando...", wait=True)
    else:
        await interaction.response.defer()
        msg = await interaction.original_response()
    
    data = await fetch_lolicon_data(params)
    
    if not data or not data.get('data'):
        await msg.edit(content="❌ No se encontraron resultados", embed=None, view=None)
        return
    
    images_data = [{
        'title': img['title'],
        'author': img['author'],
        'pid': img['pid'],
        'url': img['urls']['original'],
        'r18': img['r18'],
        'width': img['width'],
        'height': img['height'],
        'tags': img['tags'],
        'aiType': img.get('aiType', 0)
    } for img in data['data']]
    
    session_id = SessionManager.create_session(images_data, interaction.user.id)
    
    view = LoliconSearchView(images_data, session_id=session_id)
    embed = await view.create_embed()
    await msg.edit(content=None, embed=embed, view=view)

@bot.event
async def on_ready():
    print(f'✅ {bot.user} conectado')
    
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)} comandos sincronizados')
    except Exception as e:
        print(f'❌ Error: {e}')
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="arte con /loli"
        )
    )
    
    bot.loop.create_task(cleanup_sessions_task())

async def cleanup_sessions_task():
    while True:
        await asyncio.sleep(300)
        SessionManager.cleanup_expired_sessions()
        if len(active_sessions) > 0:
            print(f"🧹 Sesiones activas: {len(active_sessions)}")

@bot.tree.command(name="loli", description="Busca imágenes de anime usando Lolicon API")
@app_commands.describe(
    tags="Tags para buscar (separados por comas)",
    num="Número de imágenes (1-20)",
    r18="Filtro R18 (0=Safe, 1=R18, 2=Ambos)"
)
async def loli_command(interaction: discord.Interaction, tags: Optional[str] = None, num: int = 10, r18: int = 0):
    is_dm = interaction.guild is None
    
    if r18 == 1 and not is_dm and not interaction.channel.nsfw:
        await interaction.response.send_message("⚠️ Las imágenes R18 solo pueden buscarse en canales NSFW", ephemeral=True)
        return
    
    params = {
        'r18': min(max(r18, 0), 2),
        'num': min(max(num, 1), 20),
        'size': ['original'],
        'proxy': 'i.yuki.sh',
    }
    
    if tags:
        params['tag'] = [t.strip() for t in tags.split(',') if t.strip()]
    
    await search_and_send_images(interaction, params, is_dm)

@bot.tree.command(name="loli_random", description="Imágenes aleatorias de anime")
@app_commands.describe(num="Número de imágenes (1-20)")
async def loli_random_command(interaction: discord.Interaction, num: int = 5):
    popular_tags = ["girl", "solo", "blue_archive", "genshin", "original", 
                   "landscape", "fantasy", "maid", "swimsuit", "twintails"]
    
    params = {
        'r18': 0,
        'num': min(max(num, 1), 20),
        'size': ['original'],
        'tag': [random.choice(popular_tags)],
        'proxy': 'i.yuki.sh',
    }
    
    is_dm = interaction.guild is None
    await search_and_send_images(interaction, params, is_dm)

@bot.tree.command(name="loli_advanced", description="Búsqueda avanzada con más opciones")
async def loli_advanced_command(interaction: discord.Interaction):
    is_dm = interaction.guild is None
    modal = SearchModal(is_dm)
    await interaction.response.send_modal(modal)

@bot.tree.command(name="loli_sessions", description="Muestra tus sesiones activas")
async def loli_sessions_command(interaction: discord.Interaction):
    user_sessions = [s for sid, s in active_sessions.items() 
                    if sid.startswith(f"{interaction.user.id}_")]
    
    if not user_sessions:
        await interaction.response.send_message("📭 No tienes sesiones activas", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="💾 Tus Sesiones Activas",
        description=f"Tienes {len(user_sessions)} sesión(es) activa(s)",
        color=discord.Color.blue()
    )
    
    for session in user_sessions[:5]:
        time_left = session['expires_at'] - time.time()
        hours, remainder = divmod(int(time_left), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        embed.add_field(
            name=f"📁 {session['id'][-8:]}",
            value=f"**Imágenes:** {len(session['images'])}\n"
                  f"**Creada:** <t:{int(session['created_at'])}:R>\n"
                  f"**Expira en:** {hours}h {minutes}m",
            inline=True
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="loli_restore", description="Restaura una sesión desde un archivo JSON")
@app_commands.describe(json_file="Archivo JSON de sesión guardada")
async def loli_restore_command(interaction: discord.Interaction, json_file: discord.Attachment):
    await interaction.response.defer()
    
    if not json_file.filename.lower().endswith('.json'):
        await interaction.followup.send("❌ El archivo debe ser un JSON (.json)", ephemeral=True)
        return
    
    try:
        data = await json_file.read()
        session_data = json.loads(data.decode('utf-8'))
        
        required_fields = ['images', 'session_id']
        for field in required_fields:
            if field not in session_data:
                await interaction.followup.send(f"❌ El archivo no tiene el campo requerido: {field}", ephemeral=True)
                return
        
        images_data = session_data['images']
        
        if not isinstance(images_data, list):
            await interaction.followup.send("❌ El campo 'images' debe ser una lista", ephemeral=True)
            return
        
        if not images_data:
            await interaction.followup.send("❌ La sesión no contiene imágenes", ephemeral=True)
            return
        
        session_id = SessionManager.create_session(images_data, interaction.user.id)
        
        view = LoliconSearchView(images_data, session_id=session_id)
        embed = await view.create_embed()
        
        await interaction.followup.send(
            f"✅ Sesión restaurada correctamente ({len(images_data)} imágenes)",
            embed=embed,
            view=view
        )
        
    except json.JSONDecodeError:
        await interaction.followup.send("❌ Error: El archivo no es un JSON válido", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error al restaurar la sesión: {str(e)}", ephemeral=True)

@bot.tree.command(name="donate", description="¡Apoya el desarrollo del bot!")
async def donate_command(interaction: discord.Interaction):
    """Comando para donaciones"""
    embed = discord.Embed(
        title="❤️ ¡Apoya el desarrollo del bot!",
        description="Este bot se mantiene gracias a donaciones. Tu apoyo ayuda a:\n"
                   "• Mantener el servidor funcionando 24/7\n"
                   "• Añadir nuevas características\n"
                   "• Mejorar la estabilidad\n"
                   "• Pagar mejores APIs utilizadas",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="☕ Ko-fi",
        value=f"[Haz clic aquí para donar en Ko-fi]({KOFI_URL})\n"
              f"Acepta PayPal y proximamente tarjetas de crédito/débito",
        inline=False
    )
    
    embed.add_field(
        name="🎁 ¿Qué obtienes?",
        value="• Mención especial en los créditos\n"
              "• Acceso prioritario a nuevas características\n"
              "• ¡Mi eterno agradecimiento! ❤️",
        inline=False
    )
    
    embed.set_thumbnail(url=KOFI_EMBED)
    embed.set_image(url=KOFI_BUTTON)
    embed.set_footer(text="¡Gracias por considerar apoyar el proyecto!")
    
    view = DonateView()
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="loli_info", description="Información sobre el bot")
async def loli_info_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎨 Lolicon Bot - Información",
        description="Bot de Discord para buscar imágenes de anime usando Lolicon API\n"
                   f"**Versión:** 2.0.0 • **Estable desde:** <t:{int(time.time() - 86400)}:R>",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 Comandos Principales",
        value="""/loli [tags] [num] [r18] - Búsqueda básica
/loli_random [num] - Imágenes aleatorias
/loli_advanced - Búsqueda avanzada
/loli_sessions - Ver sesiones activas
/loli_restore - Restaurar sesión desde JSON
/loli_info - Esta información
/donate - ¡Apoya el desarrollo!""",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Características",
        value="""• **Sesiones de 30 minutos**
• **Guardar/restaurar** búsquedas
• **Enviar todas** las imágenes por DM
• **Sin filtro NSFW** en mensajes privados
• **Navegación completa** entre imágenes""",
        inline=False
    )
    
    embed.add_field(
        name="📊 Estadísticas",
        value=f"**Sesiones activas:** {len(active_sessions)}\n"
              f"**Servidores:** {len(bot.guilds)}\n"
              f"**Uptime:** <t:{int(time.time() - bot.latency)}:R>",
        inline=True
    )
    
    embed.add_field(
        name="💰 Apoyo",
        value="Este bot es **gratuito** pero mantenerlo tiene costes:\n"
              "• Servidor 24/7\n"
              "• Mejorar APIs premium\n"
              "• Desarrollo continuo\n\n"
              f"Considera donar con `/donate` para ayudar ❤️",
        inline=False
    )

    embed.add_field(
        name="🪪 Creditos",
        value="Desarrollado por **coder122** • Inspirado en proyectos de código abierto\n"
              "Donadores: Tu puedes aparecer aquí si donas ❤️\n"
              "Codigo abierto en [GitHub](https://github.com/coder122/lolicon-bot)",
        inline=False
    )

    embed.set_footer(
        text="¡Gracias por usar Lolicon Bot! • Desarrollado con ❤️ por coder122"
    )
    
    view = DonateView()
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.command(name="ping")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latencia:** {latency}ms\n"
                   f"**Sesiones activas:** {len(active_sessions)}\n"
                   f"**Servidores:** {len(bot.guilds)}",
        color=discord.Color.green()
    )
    
    if random.random() < 0.3:
        embed.set_footer(text="❤️ ¿Te gusta el bot? Considera donar con /donate")
    
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    embed = discord.Embed(
        title="❌ Error",
        description=f"```{str(error)}```",
        color=discord.Color.red()
    )
    await ctx.send(embed=embed, delete_after=10)

if __name__ == "__main__":
    print("🚀 Iniciando Lolicon Bot v2.0.0...")
    print(f"📊 {len(bot.guilds)} servidores conectados")
    bot.run(TOKEN)
