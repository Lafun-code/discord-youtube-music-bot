import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
from discord.ui import View, Button
import concurrent.futures

intents = discord.Intents.default()
intents.messages = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

cache = {}  # Şarkılar için cache (önbellek)
queue = []  # Kuyruk listesi
previous_player = None  # Önceki çalan parçayı saklamak için

async def get_info(url):
    with concurrent.futures.ThreadPoolExecutor() as pool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(pool, lambda: ytdl.extract_info(url, download=False))

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=1):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]  # Oynatma listesi değilse ilk giriş alınıyor

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

async def download_song(ctx, url):
    # İndirme işlemini başlatma
    ytdl.params['progress_hooks'] = [lambda d: asyncio.run_coroutine_threadsafe(report_progress(ctx, d), bot.loop)]
    await get_info(url)

async def report_progress(ctx, d):
    if d['status'] == 'downloading':
        total_bytes = d.get('total_bytes', 1)  # Total bytes, 1 ile bölme hatası almamak için
        downloaded_bytes = d.get('downloaded_bytes', 0)
        percent = (downloaded_bytes / total_bytes) * 100
        await ctx.send(f"İlerleme: {percent:.2f}%")
    elif d['status'] == 'finished':
        await ctx.send("İndirme tamamlandı!")

async def check_queue(ctx):
    if queue:
        next_player = queue.pop(0)
        ctx.voice_client.play(next_player, after=lambda e: bot.loop.create_task(check_queue(ctx)))
        await ctx.send(f'Çalınıyor: {next_player.title} [{format_duration(next_player.data.get("duration", 0))}]', view=create_player_buttons())
    else:
        await ctx.send("Şarkı bitti.")  # Butonları göstermek için

@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} olarak giriş yaptı!')

def format_duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"  # Saat, dakika, saniye
    else:
        return f"{minutes}:{seconds:02}"  # Sadece dakika ve saniye

@bot.command(name='play', help='URL veya isim ile şarkı çalar veya sıraya ekler')
async def play(ctx, *, search: str = None):
    global previous_player  # Global değişkeni kullan
    if search is None:
        await ctx.send("Lütfen çalmak istediğiniz şarkının ismini veya URL'sini girin.")
        return

    try:
        voice_channel = ctx.author.voice.channel
    except AttributeError:
        await ctx.send("Bir ses kanalında olmanız gerekiyor!")
        return

    voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)

    if not voice_client:
        await voice_channel.connect()

    async with ctx.typing():
        # Önce cache kontrol edilir
        if search in cache:
            player = cache[search]
        else:
            player = await YTDLSource.from_url(search, loop=bot.loop, stream=True)
            cache[search] = player  # Şarkıyı cache'e ekle

            # İndirme sürecini başlat
            await download_song(ctx, search)

        duration_formatted = format_duration(player.data.get('duration', 0))

        # Önceki parçayı güncelle
        previous_player = player  

        if not ctx.voice_client.is_playing():
            ctx.voice_client.play(player, after=lambda e: bot.loop.create_task(check_queue(ctx)))
            await ctx.send(f'Çalınıyor: {player.title} [{duration_formatted}]', view=create_player_buttons())
        else:
            queue.append(player)
            await ctx.send(f"{player.title} [{duration_formatted}] kuyruğa eklendi.")

def create_player_buttons():
    pause_button = Button(label="⏸️ Duraklat", style=discord.ButtonStyle.primary, custom_id="pause")
    resume_button = Button(label="▶️ Devam", style=discord.ButtonStyle.success, custom_id="resume")
    skip_button = Button(label="⏭️ Atla", style=discord.ButtonStyle.secondary, custom_id="skip")
    stop_button = Button(label="⏹️ Durdur", style=discord.ButtonStyle.danger, custom_id="stop")
    replay_button = Button(label="🔄 Tekrar Oynat (DENEYSEL)", style=discord.ButtonStyle.secondary, custom_id="replay")

    view = View()
    view.add_item(pause_button)
    view.add_item(resume_button)  
    view.add_item(skip_button)
    view.add_item(stop_button)
    view.add_item(replay_button)  # Tekrar Oynat butonunu ekledik

    return view

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        voice_client = interaction.guild.voice_client
        custom_id = interaction.data['custom_id']  # custom_id'yi burada tanımlıyoruz

        if custom_id == "pause":
            if voice_client and voice_client.is_playing():
                voice_client.pause()
                await interaction.response.send_message("Şarkı duraklatıldı.", ephemeral=True)
            else:
                await interaction.response.send_message("Hiçbir şarkı çalmıyor.", ephemeral=True)

        elif custom_id == "resume":
            if voice_client and voice_client.is_paused():
                voice_client.resume()
                await interaction.response.send_message("Şarkı devam ettirildi.", ephemeral=True)
            else:
                await interaction.response.send_message("Hiçbir şarkı duraklatılmamış.", ephemeral=True)

        elif custom_id == "skip":
            if voice_client and voice_client.is_playing():
                voice_client.stop()
                await interaction.response.send_message("Şarkı atlandı.", ephemeral=True)
            else:
                await interaction.response.send_message("Hiçbir şarkı çalmıyor.", ephemeral=True)

        elif custom_id == "stop":
            if voice_client:
                voice_client.stop()
                await voice_client.disconnect()
                await interaction.response.send_message("Şarkı durduruldu ve bot ses kanalından ayrıldı.", ephemeral=True)
            else:
                await interaction.response.send_message("Bot zaten ses kanalında değil.", ephemeral=True)

        elif custom_id == "replay":
            if voice_client.is_playing() or voice_client.is_paused():
                # Önceki şarkıyı yeniden başlat
                if previous_player:
                    voice_client.stop()  # Mevcut şarkıyı durdur
                    voice_client.play(previous_player, after=lambda e: bot.loop.create_task(check_queue(interaction.channel)))
                    await interaction.response.send_message("Önceki şarkı tekrar çalıyor.", ephemeral=True)
            else:
                await interaction.response.send_message("Hiçbir şarkı çalmıyor.", ephemeral=True)


@bot.command(name='p', help='Kısa yol: URL veya isim ile şarkı çalar veya sıraya ekler')
async def play_short(ctx, *, search: str = None):
    await play(ctx, search=search)

@bot.command(name='pause', help='Müziği duraklatır')
async def pause(ctx):
    if ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Müzik duraklatıldı.")
    else:
        await ctx.send("Müzik zaten duraklatılmış.")

@bot.command(name='resume', help='Müziği devam ettirir')
async def resume(ctx):
    if ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Müzik devam ettirildi.")
    else:
        await ctx.send("Müzik zaten çalıyor.")

@bot.command(name='nowplaying', help='Şu anda çalınan şarkıyı gösterir')
async def now_playing(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        current_song = ctx.voice_client.source
        await ctx.send(f"Şu anda çalınıyor: {current_song.title}")
    else:
        await ctx.send("Şu anda bir şarkı çalmıyor.")

@bot.command(name='skip', help='Bir sonraki şarkıya geçer')
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Bir sonraki şarkıya geçiliyor...")

        # Kuyruktaki bir sonraki şarkıyı çal
        if queue:
            next_song = queue.pop(0)
            ctx.voice_client.play(next_song, after=lambda e: print(f'Player hatası: {e}') if e else None)
            await ctx.send(f'Çalınıyor: {next_song.title}')
        else:
            await ctx.send("Kuyrukta çalacak başka şarkı yok.")
    else:
        await ctx.send("Şu anda çalan bir şarkı yok.")

@bot.command(name='ses', help='Ses seviyesini ayarlar (0-100) ve mevcut ses seviyesini gösterir')
async def volume(ctx, volume: int = None):
    if volume is None:
        current_volume = int(ctx.voice_client.source.volume * 100)
        return await ctx.send(f"Mevcut ses seviyesi: {current_volume}")

    if volume < 0 or volume > 100:
        return await ctx.send("Lütfen ses seviyesini 0 ile 100 arasında bir değer olarak girin.")

    ctx.voice_client.source.volume = volume / 100
    await ctx.send(f"Ses seviyesi {volume} olarak ayarlandı.")

@bot.command(name='playlist', help='YouTube oynatma listesini çalar')
async def playlist(ctx, url: str):
    playlist_info = await ytdl.extract_info(url, download=False)
    for video in playlist_info['entries']:
        player = await YTDLSource.from_url(video['url'], loop=bot.loop, stream=True)
        queue.append(player)
    await ctx.send(f"{len(playlist_info['entries'])} şarkı kuyruğa eklendi.")

@bot.command(name='stop', help='Çalan müziği durdurur ve ses kanalından çıkar')
async def stop(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Müzik durduruldu ve ses kanalından çıkıldı.")
    else:
        await ctx.send("Bot zaten bir ses kanalında değil.")

@bot.command(name='clearqueue', help='Şarkı kuyruğunu temizler')
async def clear_queue(ctx):
    if not queue:
        return await ctx.send("Kuyruk zaten boş.")
    
    queue.clear()
    await ctx.send("Şarkı kuyruğu temizlendi.")

@bot.command()
async def sil(ctx, amount: int):
    if ctx.author.guild_permissions.administrator:
        if amount <= 0:
            await ctx.send("Silinecek mesaj sayısı 1'den büyük olmalı.")
            return

        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"{len(deleted)} mesaj başarıyla silindi.", delete_after=5)
    else:
        await ctx.send("Bu komutu sadece adminler kullanabilir.")


@bot.command(name='komutlar', help='Botun sunduğu tüm komutları listeler')
async def komutlar(ctx):
    commands_list = """
    **Komutlar:**
    !play [şarkı adı veya URL] - Şarkı çalar. !p ile de kullanılabilir.
    !stop - Durur.
    !pause - Müziği duraklatır.
    !resume - Müziği devam ettirir.
    !nowplaying - Şu anda çalınan şarkıyı gösterir.
    !queue [şarkı adı veya URL] - Şarkıyı sıraya ekler.
    !skip - Bir sonraki şarkıya geçer.
    !ses [0-100] - Ses seviyesini ayarlar. Anlık ses seviyesini gösterir.
    !playlist [YouTube oynatma listesi URL'si] - Oynatma listesini çalar.
    !komutlar - Botun sunduğu komutları gösterir.
    !clearqueue - Sırayı Temizler.
    !sil x kadar mesaj siler. (ADMIN)
    """
    await ctx.send(commands_list)

bot.run('YOUR_DISCORD_BOT_TOKEN')
