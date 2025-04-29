import discord
from discord.ext import commands
from discord.ext import tasks
import random
import asyncio
import yt_dlp as youtube_dl
from datetime import datetime
from pytz import timezone
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
import io
# Khởi tạo các intents và bot
# Khởi tạo các intents và bot
intents = discord.Intents.default()  # Khởi tạo intents
intents.message_content = True  # Bật quyền truy cập nội dung tin nhắn

# Khởi tạo bot với intents và vô hiệu hóa lệnh help mặc định
bot = commands.Bot(command_prefix=commands.when_mentioned_or("y!", "Y!"), intents=intents, help_command=None)
# Khai báo song_queues
song_queues = {}
# Modal thêm nhạc
class ThemNhacModal(discord.ui.Modal, title="Thêm bài hát vào hàng chờ"):
    ten_bai_hat = discord.ui.TextInput(
        label="Nhập tên hoặc link bài hát",
        placeholder="Ví dụ: Sơn Tùng MTP - Chúng Ta Của Hiện Tại",
        required=True)

    def __init__(self, ctx, voice_client):
        super().__init__()
        self.ctx = ctx
        self.voice_client = voice_client

    # async def on_submit(self, interaction: discord.Interaction):
        query = self.ten_bai_hat.value
        guild_id = interaction.guild.id

        if guild_id not in song_queues:
            song_queues[guild_id] = []
        song_queues[guild_id].append(query)

async def some_function(interaction, query):
    await interaction.response.send_message(
        f"🎵 Đã thêm **{query}** vào danh sách phát!", ephemeral=True)

# Các nút điều khiển nhạc
from discord import PartialEmoji, ButtonStyle, Interaction, ui

class NutDieuKhien(discord.ui.View):
    def __init__(self, ctx, voice_client):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.voice_client = voice_client

        # Nút Danh sách chờ (dùng emoji tùy chỉnh từ bot)
        nut_xem_hang_cho = discord.ui.Button(
            label="Danh sách chờ",
            style=ButtonStyle.secondary,
            emoji=PartialEmoji(name="mh", id=1366041952310526184)  # Thay name nếu cần
        )
        nut_xem_hang_cho.callback = self.nut_xem_hang_cho_callback
        self.add_item(nut_xem_hang_cho)

    @ui.button(label="Tạm dừng", style=ButtonStyle.secondary, emoji=PartialEmoji(name="tamdung", id=1366076936815902760))  # Tạm dừng
    async def nut_tam_dung(self, interaction: Interaction, button: ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            await ghi_log(self.ctx.bot, interaction.user, "Tạm dừng nhạc")
            await interaction.response.send_message("⏸ Đã tạm dừng nhạc", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có bài hát nào đang phát", ephemeral=True)

    @ui.button(label="Tiếp tục", style=ButtonStyle.secondary, emoji=PartialEmoji(name="tieptuc", id=1366055566597947402))  # Tiếp tục
    async def nut_tiep_tuc(self, interaction: Interaction, button: ui.Button):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            await ghi_log(self.ctx.bot, interaction.user, "Tiếp tục phát nhạc")
            await interaction.response.send_message("▶ Đã tiếp tục phát nhạc", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có bài hát nào đang tạm dừng", ephemeral=True)

    @ui.button(label="Bỏ qua", style=ButtonStyle.secondary, emoji=PartialEmoji(name="boqua", id=1366056001861849148))  # Bỏ qua
    async def nut_bo_qua(self, interaction: Interaction, button: ui.Button):
        if self.voice_client.is_playing():
            self.voice_client.stop()
            await ghi_log(self.ctx.bot, interaction.user, "Bỏ qua bài hát")
            await interaction.response.send_message("⏭ Đã bỏ qua bài hát!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Không có bài hát nào để bỏ qua!", ephemeral=True)

    @ui.button(label="Thêm nhạc", style=ButtonStyle.secondary, emoji=PartialEmoji(name="themnhac", id=1366056464229204049))  # Thêm nhạc
    async def nut_them_nhac(self, interaction: Interaction, button: ui.Button):
        modal = ThemNhacModal(ctx=self.ctx, voice_client=self.voice_client)
        await interaction.response.send_modal(modal)

    @ui.button(label=" Dừng", style=ButtonStyle.secondary, emoji=PartialEmoji(name="dung", id=1366076202086961183))  # dừng
    async def nut_dung(self, interaction: Interaction, button: ui.Button):
        try:
            if self.voice_client and self.voice_client.is_connected():
                await self.voice_client.disconnect()
                song_queues.pop(interaction.guild.id, None)
                await interaction.response.send_message("⏹ Đã dừng phát và rời khỏi kênh thoại", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Bot không ở trong kênh thoại nào", ephemeral=True)
        except Exception as e:
            print(f"Lỗi khi dừng nhạc: {str(e)}")

    # Callback cho nút Danh sách chờ
    async def nut_xem_hang_cho_callback(self, interaction: Interaction):
        guild_id = interaction.guild.id
        queue = song_queues.get(guild_id, [])
        if queue:
            danh_sach = '\n'.join([f"{idx+1}. {song}" for idx, song in enumerate(queue)])
            await interaction.response.send_message(f"📜 **Danh sách chờ:**\n{danh_sach}", ephemeral=True)
        else:
            await interaction.response.send_message("📝 Danh sách chờ trống!", ephemeral=True)

async def ghi_log(bot, user, action, details=None):
    try:
        log_channel = bot.get_channel(1341825853813690378)
        if not log_channel:
            return

        vn_tz = timezone('Asia/Ho_Chi_Minh')
        thoi_gian = datetime.now(vn_tz).strftime("%H:%M:%S %d/%m/%Y")

        embed = discord.Embed(
            title="🎵 Bot Music Log",
            color=discord.Color.from_rgb(255, 182, 193),
            timestamp=datetime.now(vn_tz)
        )
        embed.add_field(name="Người dùng", value=f"{user.name} (`{user.id}`)", inline=True)
        embed.add_field(name="Hành động", value=action, inline=True)

        if details:
            embed.add_field(name="Chi tiết", value=details, inline=False)

        thong_tin_kenh = "Không có"
        if hasattr(user, 'voice') and user.voice and user.voice.channel:
            thong_tin_kenh = f"<#{user.voice.channel.id}>"
        embed.add_field(name="Kênh", value=thong_tin_kenh, inline=True)
        embed.add_field(name="Thời gian", value=thoi_gian, inline=True)

        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Lỗi khi ghi log: {str(e)}")

@bot.event
async def on_ready():
    print(f'Đã đăng nhập với tên {bot.user.name}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="MH Dev Lệnh Y!help"))

# Lệnh phát nhạc (play)
@bot.command(name='play', aliases=['p'])
async def phat_nhac(ctx, *, query: str):
    await ghi_log(bot, ctx.author, "Phát nhạc", f"Query: {query}")

    if not ctx.author.voice:
        await ctx.send("❌ Bạn cần vào một kênh thoại trước!")
        return

    try:
        channel = ctx.author.voice.channel

        if ctx.voice_client is None:
            voice_client = await channel.connect()
        else:
            await ctx.voice_client.move_to(channel)
            voice_client = ctx.voice_client

        guild_id = ctx.guild.id
        if guild_id not in song_queues:
            song_queues[guild_id] = []

        if voice_client.is_playing() or voice_client.is_paused():
            song_queues[guild_id].append(query)
            await ctx.send("<a:NKV_book:1366040484446867517> Đã thêm vào danh sách phát!")
            return

        await phat_bai_hat(ctx, voice_client, query)

    except Exception as e:
        await ctx.send(f"❌ Có lỗi xảy ra: {str(e)}")
        if ctx.voice_client:
            await ctx.voice_client.disconnect()

async def phat_bai_hat(ctx, voice_client, query):
    await ctx.send("<a:xxx_6:1365209797867339818> Đang tìm kiếm nhạc...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'nocheckcertificate': True,
        'default_search': 'auto',
        'quiet': True,
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            if 'youtube.com' in query or 'youtu.be' in query:
                info = ydl.extract_info(query, download=False)
            else:
                result = ydl.extract_info(f"ytsearch:{query}", download=False)
                if not result or not result.get('entries'):
                    await ctx.send("❌ Không tìm thấy bài hát!")
                    return
                info = result['entries'][0]

            url = info['url']
            thoi_luong = int(info.get('duration', 0))
            phut = thoi_luong // 60
            giay = thoi_luong % 60
            duration = f"{phut}:{giay:02d}"

            embed = discord.Embed(
                title="Thông tin bài hát",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.add_field(name="Tên bài hát", value=info.get('title', 'Không có thông tin'), inline=False)
            embed.add_field(name="Thời lượng", value=duration, inline=True)
            embed.add_field(name="Đang phát ở", value=voice_client.channel.name, inline=True)
            embed.set_image(url=info.get('thumbnail', ''))

            vietnam_timezone = timezone('Asia/Ho_Chi_Minh')
            time_requested = datetime.now(vietnam_timezone).strftime("%H:%M:%S")
            embed.set_footer(text=f"Yêu cầu bởi: {ctx.author.display_name} lúc {time_requested}")

            await ctx.send(embed=embed, view=NutDieuKhien(ctx, voice_client))

            ffmpeg_options = {
                'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                'options': '-vn'
            }

            source = await discord.FFmpegOpusAudio.from_probe(url, **ffmpeg_options)
            voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(phat_bai_tiep(ctx, voice_client), bot.loop))

    except Exception as e:
        await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)}")
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()

async def phat_bai_tiep(ctx, voice_client):
    guild_id = ctx.guild.id
    if guild_id in song_queues and song_queues[guild_id]:
        bai_tiep = song_queues[guild_id].pop(0)
        await phat_bai_hat(ctx, voice_client, bai_tiep)
    else:
        await asyncio.sleep(300)  # 5 phút
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()

# ====== Thêm lệnh viết tắt skip, autoplay, stop ======
@bot.command(name='skip', aliases=['s'])
async def bo_qua(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("<a:xxx_muiten:1357713437815210094> Đã bỏ qua bài hát!")

@bot.command(name='stop', aliases=['st'])
async def dung(ctx):
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
        await ctx.send("<a:xxx_muiten:1357713437815210094> Đã dừng và rời khỏi kênh thoại!")

import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio

# Danh sách 100 bài nhạc chill (thêm bài nhạc vào danh sách này)
chill_tracks = [
    "https://www.youtube.com/watch?v=PKWeqACICDw",  # Example chill track 1
    "https://www.youtube.com/watch?v=bKIxd3dcYoA",  # Example chill track 2
    "https://www.youtube.com/watch?v=Ch9EUW0_aSI",  # Example chill track 3
    "https://www.youtube.com/watch?v=BhZ_aoCvMM8",  # Example chill track 4
    "https://www.youtube.com/watch?v=PQsWzCT8En8",  # Example chill track 5
    "https://www.youtube.com/watch?v=UJCuya1SRFk",  # Example chill track 6
    "https://www.youtube.com/watch?v=WegqhgGdTYA",  # Example chill track 7
    "https://www.youtube.com/watch?v=2TVXr5NOONE",  # Example chill track 8
    "https://www.youtube.com/watch?v=BTBrvavD4GA",  # Example chill track 9
    "https://www.youtube.com/watch?v=IQrWE4vh3BU",  # Example chill track 10
    "https://www.youtube.com/watch?v=HtXmD0PjfCM",  # Example chill track 11
    "https://www.youtube.com/watch?v=9vktlsjzJ6s",  # Example chill track 12
    "https://www.youtube.com/watch?v=H8GQpfsm72M",  # Example chill track 13
    "https://www.youtube.com/watch?v=z9H_NwWluVQ",  # Example chill track 14
    "https://www.youtube.com/watch?v=upRA1Lbg8lk",  # Example chill track 15
    "https://www.youtube.com/watch?v=TuKW46cRbBI",  # Example chill track 16
    "https://www.youtube.com/watch?v=gABxXOhZZ0Y",  # Example chill track 17
    "https://www.youtube.com/watch?v=NLJygtXLUtM",  # Example chill track 18
    "https://www.youtube.com/watch?v=z1o-dGkuINM",  # Example chill track 19
    "https://www.youtube.com/watch?v=hnxKVWfvuKg",  # Example chill track 20
]

# Biến để theo dõi số bài nhạc đã phát
current_play_count = 0

# Hàm phát nhạc từ URL
async def play_music(ctx, voice_client, url, loop=False):
    global current_play_count

    ydl_opts = {
        'format': 'bestaudio/best',
        'nocheckcertificate': True,
        'default_search': 'auto',
        'quiet': True,
    }

    try:
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            song_url = info['url']
            song_title = info['title']  # Tiêu đề bài hát
            song_thumbnail = info['thumbnail']  # Ảnh bìa bài hát
            song_duration = info['duration']  # Thời lượng bài hát

        # Tạo Embed hiển thị thông tin bài hát
        embed = discord.Embed(
            title=f"**__Chill Nào :__** {song_title}",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.add_field(name="Thời gian", value=f"{song_duration // 60}:{song_duration % 60:02d}", inline=True)
        embed.add_field(name="Đang phát ở", value=f"{ctx.author.voice.channel.name}", inline=True)
        embed.set_image(url=song_thumbnail)  # Hiển thị ảnh bìa
        embed.set_footer(text=f"Yêu cầu bởi: {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }


        source = await discord.FFmpegOpusAudio.from_probe(song_url, **ffmpeg_options)
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(ctx, voice_client, loop), bot.loop))

        current_play_count += 1  # Tăng số bài đã phát

    except Exception as e:
        await ctx.send(f"❌ Lỗi khi phát nhạc: {str(e)}")
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
# Hàm phát bài tiếp theo từ danh sách nhạc
async def play_next_song(ctx, voice_client, loop=False):
    global current_play_count

    if current_play_count >= 20:  # Nếu đã phát 20 bài, bắt đầu lại từ bài đầu tiên
        current_play_count = 0  # Reset lại số bài đã phát

    if chill_tracks:
        next_song = chill_tracks.pop(0)  # Lấy bài nhạc tiếp theo từ danh sách
        await play_music(ctx, voice_client, next_song, loop)
    else:
        await asyncio.sleep(300)  # Nếu không có bài nhạc nào, chờ 5 phút
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
# Lệnh autoplay để tự động phát nhạc
@bot.command(name='autoplay', aliases=['ap'])
async def autoplay(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Bạn cần vào một kênh thoại trước!")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        voice_client = await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)
        voice_client = ctx.voice_client
     
    # Đổi trạng thái bot thành "Đang nghe nhạc của [Tên bạn]"
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=f"Đại Ka MH Đang Sửa Bot"))

    await ctx.send("<a:tho_chill:1366293196979699712>****chill cùng tôi nhé!****<a:tho_chill:1366293196979699712>")

    # Bắt đầu phát nhạc đầu tiên từ danh sách
    await play_music(ctx, voice_client, chill_tracks.pop(0), loop=True)  # Bật chế độ loop
 
# ====================================================
 
# ====== Lệnh 24/7 LOFI ======
@bot.command(name='247', aliases=['lofi'])
async def che_do_247(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Bạn cần vào một kênh thoại trước!")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        voice_client = await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)
        voice_client = ctx.voice_client

    await play_lofi(voice_client)
    await ctx.send("🎶 Đã bật chế độ phát nhạc 24/7!")

async def play_lofi(voice_client):
    # Danh sách các liên kết stream Lofi
    lofi_stream_urls = [
        "https://www.youtube.com/watch?v=eJ5-Z4-CYUM",  # Nhạc Lofi Buồn Hot Nhất Hiện Nay
        "https://www.youtube.com/watch?v=qRNOWYqg29U",  # Nhạc Buồn Chill 
        "https://www.youtube.com/watch?v=TGQ0IsHoJ5s",  # Nhạc Chill Dễ Ngủ 2025
        "https://www.youtube.com/watch?v=MkQjF0f2Y38",  # Vì Ngày Em Đẹp Nhất Là Ngày Anh Mất Em Lofi 
        "https://www.youtube.com/watch?v=iw-a-ywJzew",  # Nhạc Lofi Chill 
        "https://www.youtube.com/watch?v=K4PU0ssK-Qo"   # Nhạc Chill Dễ Ngủ - 2h Chìm Vào Những Bản Lofi 
    ]

    try:
        # Lấy URL stream ngẫu nhiên từ danh sách
        stream_url = random.choice(lofi_stream_urls)
        
        # Tải thông tin video từ YouTube
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto'
        }
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(stream_url, download=False)
            url = info['url']

        # Tùy chọn FFmpeg cho việc phát âm thanh
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        
        # Tạo và phát audio
        source = await discord.FFmpegOpusAudio.from_probe(url, **ffmpeg_options)
        voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_lofi(voice_client), bot.loop))

    except Exception as e:
        print(f"Lỗi khi phát lofi: {e}")
@bot.command(name='av', aliases=['avatar'])
async def avatar(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    embed = discord.Embed(
        title=f"Ảnh đại diện của {member.display_name}",
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.set_image(url=member.display_avatar.url)
    embed.set_footer(text=f"Yêu cầu bởi Dev Yimi", icon_url=ctx.author.display_avatar.url)

    await ctx.send(embed=embed)
    
# ====================================================

@bot.command(name='setname', aliases=['sn', 'rename'])
@commands.has_permissions(manage_nicknames=True)
async def set_name(ctx, member: discord.Member, *, nickname: str):
    try:
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Đã đổi tên {member.mention} thành **{nickname}**!")
    except discord.Forbidden:
        await ctx.send("❌ Bot không đủ quyền để đổi tên người này!")
    except Exception as e:
        await ctx.send(f"❌ Đổi tên thất bại: {e}")
        
# ====================================================

@bot.command(name='support')
async def support(ctx):
    embed = discord.Embed(
        title="💬 Hỗ trợ Yimi Music",
        description="Nếu bạn cần hỗ trợ hoặc báo lỗi, hãy tham gia server support của chúng tôi!\n\n🔗 [Tham gia Support Server](https://discord.gg/xomxamxi)",
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.set_footer(text="Yimi Music Premium", icon_url=ctx.guild.me.display_avatar.url)
    await ctx.send(embed=embed)

# ====================================================

@bot.command(name='banner', aliases=['bìa', 'bia'])
async def banner(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    try:
        user = await bot.fetch_user(member.id)
        banner_url = user.banner.url if user.banner else None

        if banner_url:
            embed = discord.Embed(
                title=f"🎀 Banner của {member.display_name}",
                color=discord.Color.from_rgb(255, 182, 193)
            )
            embed.set_image(url=banner_url)
            embed.set_footer(text="Yimi Music Premium", icon_url=ctx.guild.me.display_avatar.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ {member.mention} hiện không có banner!")

    except Exception as e:
        await ctx.send(f"❌ Đã xảy ra lỗi: {e}")

# ====================================================

# --- Biến toàn cục ---
user_data = {}  # Dùng dict để lưu XP và Level tạm thời
xp_per_level = 1000  # 1 cấp cần 1000 XP

# --- Cộng XP mỗi khi nhắn tin ---
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id

    # Nếu user chưa có dữ liệu
    if user_id not in user_data:
        user_data[user_id] = {"xp": 0, "level": 1, "last_add": datetime.now()}

    # Kiểm tra cooldown 10 giây
    now = datetime.now()
    if (now - user_data[user_id]["last_add"]).total_seconds() >= 10:
        # Tăng XP ngẫu nhiên từ 15 - 25
        xp_gain = random.randint(15, 25)
        user_data[user_id]["xp"] += xp_gain
        user_data[user_id]["last_add"] = now

        # Check lên cấp
        if user_data[user_id]["xp"] >= user_data[user_id]["level"] * xp_per_level:
            user_data[user_id]["xp"] = 0
            user_data[user_id]["level"] += 1
            # Gửi chúc mừng
            await message.channel.send(f"🎉 {message.author.mention} đã lên cấp **{user_data[user_id]['level']}**!")

    await bot.process_commands(message)

# --- Lệnh profile hiển thị ---
import discord
from discord.ext import commands
import aiohttp
import io
from PIL import Image, ImageDraw, ImageFont, ImageOps

@bot.command(name='profile', aliases=['pf'])
async def profile(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author

    # Tải avatar và background anime
    async with aiohttp.ClientSession() as session:
        async with session.get(str(member.display_avatar.url)) as resp:
            avatar_bytes = await resp.read()

        anime_bg_url = "https://i.pinimg.com/736x/7f/6d/c5/7f6dc5a74f7a8b2bd60d3adf4b1a3338.jpg"  # Link background anime đẹp
        async with session.get(anime_bg_url) as bg_resp:
            bg_bytes = await bg_resp.read()

    # Mở avatar và bo tròn
    avatar = Image.open(io.BytesIO(avatar_bytes)).resize((150, 150)).convert('RGBA')
    mask = Image.new('L', (150, 150), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, 150, 150), fill=255)
    avatar = ImageOps.fit(avatar, (150, 150))
    avatar.putalpha(mask)

    # Tạo viền avatar
    border_size = 8
    bordered_avatar = Image.new('RGBA', (avatar.width + border_size*2, avatar.height + border_size*2), (255, 255, 255, 0))
    mask_with_border = Image.new('L', (avatar.width + border_size*2, avatar.height + border_size*2), 0)
    draw_border = ImageDraw.Draw(mask_with_border)
    draw_border.ellipse((0, 0, avatar.width + border_size*2, avatar.height + border_size*2), fill=255)
    bordered_avatar.paste(avatar, (border_size, border_size), avatar)

    # Mở background
    background = Image.open(io.BytesIO(bg_bytes)).resize((600, 300)).convert('RGBA')
    draw = ImageDraw.Draw(background)

    # Font chữ
    try:
        font_big = ImageFont.truetype("arial.ttf", 35)
        font_small = ImageFont.truetype("arial.ttf", 22)
    except:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Dán avatar
    background.paste(bordered_avatar, (30, 75), mask_with_border)

    # Random level, xp, rank
    level = random.randint(1, 50)
    xp = random.randint(100, 5000)
    ranks = ['Newbie', 'Rising Star', 'Pro Player', 'Legendary', 'Mythical']
    rank = random.choice(ranks)

    # Hàm vẽ chữ có viền
    def draw_text_with_outline(draw, position, text, font, text_color, outline_color='black', outline_width=2):
        x, y = position
        for ox in range(-outline_width, outline_width+1):
            for oy in range(-outline_width, outline_width+1):
                draw.text((x+ox, y+oy), text, font=font, fill=outline_color)
        draw.text((x, y), text, font=font, fill=text_color)

    # Viết tên + level + xp + rank
    draw_text_with_outline(draw, (220, 60), f"{member.display_name}", font_big, (255, 255, 255))
    draw_text_with_outline(draw, (220, 110), f"🏅 Cấp bậc: {rank}", font_small, (255, 255, 255))
    draw_text_with_outline(draw, (220, 150), f"✨ Level: {level}", font_small, (255, 255, 255))
    draw_text_with_outline(draw, (220, 190), f"⚡ XP: {xp} / 5000", font_small, (255, 255, 255))

    # Thanh XP
    bar_x, bar_y = 220, 230
    bar_width = 320
    bar_height = 20
    filled_width = int((xp / 5000) * bar_width)

    draw.rectangle((bar_x, bar_y, bar_x + bar_width, bar_y + bar_height), fill=(211, 211, 211))  # nền xám nhạt
    draw.rectangle((bar_x, bar_y, bar_x + filled_width, bar_y + bar_height), fill=(255, 105, 180))  # thanh màu hồng

    # Lưu hình
    with io.BytesIO() as image_binary:
        background.save(image_binary, 'PNG')
        image_binary.seek(0)

        file = discord.File(fp=image_binary, filename='profile.png')

        embed = discord.Embed(
            title="🌸 Hồ sơ thành viên - Yimi Music",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        embed.set_image(url="attachment://profile.png")
        embed.set_footer(text=f"Yêu cầu bởi {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(file=file, embed=embed)
# ====================================================

@bot.command(name='chat')
async def say(ctx, *, message: str):
    await ctx.message.delete()  # Xóa tin nhắn của người gọi lệnh
    await ctx.send(message)      # Gửi lại nội dung

# ====================================================
import calendar
from datetime import datetime
import discord
import requests

# API key của bạn từ OpenWeatherMap
API_KEY = '63ec0ccb1fd3739a87941753e8e13e20'

@bot.command(name='lich')
async def lich(ctx):
    # Lấy ngày tháng hiện tại
    today = datetime.today()
    month = today.month
    year = today.year
    cal = calendar.month(year, month)

    # Lấy ngày, tháng, năm và giờ hiện tại
    current_date = today.strftime("%d/%m/%Y")
    current_time = today.strftime("%H:%M:%S")

    # Gửi yêu cầu tới OpenWeatherMap API để lấy nhiệt độ tại Việt Nam
    city = "Hanoi"  # Bạn có thể thay đổi thành các thành phố khác nếu cần
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric&lang=vi"
    
    response = requests.get(url)
    data = response.json()

    if data["cod"] == 200:
        temperature = data["main"]["temp"]
        weather_description = data["weather"][0]["description"]
    else:
        temperature = "Không thể lấy dữ liệu"
        weather_description = "Không có thông tin"

    # Tạo Embed với màu hồng và hiển thị thông tin
    embed = discord.Embed(
        title=f"Lịch tháng {month}/{year}",
        description=f"```{cal}```",
        color=discord.Color.from_rgb(255, 182, 193)  # Màu hồng
    )
    
    embed.add_field(name="Ngày tháng", value=current_date, inline=True)
    embed.add_field(name="Giờ hiện tại", value=current_time, inline=True)
    embed.add_field(name="Nhiệt độ tại Hà Nội Việt Nam ", value=f"{temperature}°C - {weather_description}", inline=False)
    
    await ctx.send(embed=embed)

    # ====================================================
@bot.command(name='quote')
async def quote(ctx):
    quotes = [
        "<a:p_ccl8:1366233647174258809> Đừng để nỗi sợ ngăn bạn lại. Cứ đi đi!",
        "<a:p_ccl4:1366233833464266852>  Người thành công không bao giờ bỏ cuộc.",
        "<a:p_ccl5:1366234012120776786>  Hãy tin vào hành trình của chính mình.",
        "<a:p_ccl9:1366234157403078758>  Cuộc sống giống như một cuốn sách, mỗi ngày là một trang mới.",
        "<a:p_ccl7:1366234268266795093>  Khi bạn dừng lại, hãy nhớ lý do bạn bắt đầu."
        ]
    random_quote = random.choice(quotes)

    embed = discord.Embed(
        title="<a:p_zppl24:1366234463939461200>  Yimi Quote <a:p_zppl24:1366234463939461200> ",
        description=random_quote,
        color=discord.Color.from_rgb(255, 182, 193)
    )
    embed.set_footer(text="✨ Luôn lạc quan và yêu đời nhé!", icon_url=ctx.guild.me.display_avatar.url)
    
    await ctx.send(embed=embed)
    # ====================================================

    # ====================================================
# Lệnh help
@bot.command(name='help')
async def help_command(ctx) :
    help_texts = {  
        "<a:nhac:1366094643846185031> Phát nhạc": "`y!play <tên>` hoặc `y!p <tên>`",
        "<a:skip:1366097992830160957> Bỏ qua bài hát": "`y!skip` hoặc `y!s`",
        "<a:cut:1366098202239176876> Dừng nhạc": "`y!stop` hoặc `y!st`",
        "<a:auto:1366098411975348334> Auto Play": "`y!autoplay` hoặc `y!ap`",
        "<a:chill:1366098612135661650> Phát Lofi 24/7": "`y!247`",
        "<a:xxx_5:1365209715336024124> Các lệnh check": "`y!profile`",
        "<a:check:1366098880889884723> Xem avatar & banner": "`y!banner @user` hoặc `y!bia @user`",
        "<a:doiten:1366099169332297870> Đổi nickname": "`y!setname @user <nickname>`",
        "<a:sp:1366099407975743591> Hỗ trợ Bot": "`y!support`",
        "<a:chill:1366098612135661650> Chat": "`y!chat <nội dung>` — Bot chat thay bạn",
        "<a:xxx_s1:1356891549480386691> Say": "`y!say <nội dung>` — Bot đọc văn bản thay bạn", 
        "<a:xxx_thobonla:1359158478093942915> các lệnh hay ho ": "`y!profile` -  `y!quote` ",
        "<a:1702_dongho:1366335769597313024> ngày giờ và nhiệt độ ": " `y!lich` ",
        "<a:xxx_hopqua:1358449105281749127>  mở quà từ gacha ": " `y!gacha` ",
    }
    
    # Tiếp tục với các lệnh khác trong hàm
    embed = discord.Embed(
        title="Hướng dẫn sử dụng Bot",
        description="Dưới đây là các lệnh bạn có thể sử dụng:",
        color=discord.Color.from_rgb(255, 182, 193)
    )
    
    for name, desc in help_texts.items():
        embed.add_field(name=name, value=desc, inline=False)  # Thêm các lệnh vào embed

    await ctx.send(embed=embed)
    # ==================================================

import discord
from discord.ext import commands
import os
import sys
import requests
import os

# Lệnh thay đổi Bio
@bot.command()
async def set_bio(ctx, *, bio: str):
    """Thay đổi tiểu sử (status) của bot."""
    try:
        # Thay đổi bio (status)
        await bot.change_presence(activity=discord.Game(name=bio))
        await ctx.send(f"Tiểu sử của bot đã được thay đổi thành: {bio}")
    except Exception as e:
        await ctx.send(f"Đã xảy ra lỗi khi thay đổi tiểu sử: {str(e)}")

# Lệnh reset (khởi động lại bot)
@bot.command()
async def reset(ctx):
    """Lệnh khởi động lại bot."""
    await ctx.send("Bot đang khởi động lại...")
    os.execv(sys.executable, ['python'] + sys.argv)  # Khởi động lại script bot
 # ====================================================
import discord
from discord.ext import commands
import random

# Lưu trữ ID của admin bot chính
admin_id = "1352385546470691009"  # Thay 'YOUR_ADMIN_ID' bằng ID Discord của admin chính (chỉ người này mới có quyền cấp admin)

# Giả lập kho thẻ của người chơi
user_inventory = {}
user_daily_quota = {}  # Lưu trữ lượt quay miễn phí cho mỗi người chơi
user_ryo = {}  # Lưu trữ số tiền Ryo của người chơi
admin_list = {}  # Lưu trữ danh sách những người có quyền admin

# Danh sách thẻ có thể nhận được từ gacha, bao gồm cả hình ảnh và giải thưởng
cards = [
    {"name": "Chunin Kakashi", "strength": 380, "rank": "Chunin", "rarity": "giải ba", "image_url": "https://i.imgur.com/KqKjvNb.jpeg", "reward": "20.000 <:OWO:1359511986467115039>"},
    {"name": "Uchiha Sasuke", "strength": 590, "rank": "Jounin", "rarity": "giải nhì", "image_url": "https://i.imgur.com/GzACF70.png", "reward": "500.000 <:OWO:1359511986467115039>"},
    {"name": "Pain", "strength": 570, "rank": "Jounin", "rarity": "giải ba", "image_url": "https://i.imgur.com/ilrcwI8.jpeg", "reward": "20.000 <:OWO:1359511986467115039>"},
    {"name": "Naruto Uzumaki", "strength": 650, "rank": "Legendary", "rarity": "giải nhất", "image_url": "https://i.imgur.com/TkKEo8H.jpeg", "reward": "2.000.000 <:OWO:1359511986467115039>"},
    {"name": "Itachi Uchiha", "strength": 700, "rank": "Legendary", "rarity": "giải nhì", "image_url": "https://i.imgur.com/QbdTzgr.jpeg", "reward": "500.000 <:OWO:1359511986467115039>"}
]

# Lệnh để admin chính cấp quyền admin cho người khác
@bot.command()
async def add_admin(ctx, member: discord.Member):
    """Cấp quyền admin cho người chơi (chỉ admin chính)."""
    if str(ctx.author.id) != admin_id:
        await ctx.send("Bạn không có quyền sử dụng lệnh này!")
        return

    # Thêm người chơi vào danh sách admin
    admin_list[member.id] = True
    await ctx.send(f"{member.name} đã được cấp quyền admin!")

# Lệnh kiểm tra xem người chơi có phải admin hay không
@bot.command()
async def is_admin(ctx, member: discord.Member):
    """Kiểm tra người chơi có phải admin hay không."""
    if member.id in admin_list:
        await ctx.send(f"{member.name} là admin.")
    else:
        await ctx.send(f"{member.name} không phải là admin.")

# Lệnh thêm lượt quay cho người chơi (chỉ admin mới có quyền)
@bot.command()
async def add_luot_quay(ctx, member: discord.Member, amount: int):
    """Cấp thêm lượt quay cho người chơi (chỉ admin chính)."""
    if str(ctx.author.id) != admin_id:
        await ctx.send("Bạn không có quyền sử dụng lệnh này!")
        return

    if member.id not in user_daily_quota:
        user_daily_quota[member.id] = 0  # Nếu người chơi chưa có dữ liệu, khởi tạo
    user_daily_quota[member.id] += amount  # Thêm số lượt quay cho người chơi
    await ctx.send(f"{member.name} đã được cấp thêm {amount} lượt quay!")

# Lệnh mua gacha
@bot.command()
async def gacha(ctx, use_ryo: bool = False):
    """Mở gacha để nhận thẻ ngẫu nhiên."""
    # Kiểm tra nếu người chơi có lượt quay miễn phí hoặc đủ Ryo để quay
    if ctx.author.id not in user_daily_quota:
        user_daily_quota[ctx.author.id] = 1  # Mỗi người chơi có một lượt quay miễn phí mỗi ngày
    if ctx.author.id not in user_ryo:
        user_ryo[ctx.author.id] = 50000  # Tiền khởi điểm

    # Kiểm tra lượt quay miễn phí
    if user_daily_quota[ctx.author.id] > 0:
        can_gacha = True
        user_daily_quota[ctx.author.id] -= 1  # Dùng một lượt quay miễn phí
        await ctx.send("Bạn đã sử dụng lượt quay")
    elif use_ryo and user_ryo[ctx.author.id] >= 10000:  # Nếu người chơi muốn dùng tiền để mua thêm lượt quay
        can_gacha = True
        user_ryo[ctx.author.id] -= 10000  # Trừ đi 10000 Ryo để mua lượt quay
        await ctx.send("Bạn đã sử dụng 10,000 Ryo để mua một lượt quay!")
    else:
        can_gacha = False
        await ctx.send("Bạn không còn lượt quay miễn phí và không đủ Ryo để mua lượt quay.")

    if not can_gacha:
        # Nếu không đủ điều kiện quay, hiển thị thông báo thất bại
        embed = discord.Embed(
            title="🎉 Bạn không nhận được gì cả!",
            description="Bạn không có đủ lượt quay hoặc Ryo để thực hiện quay.",
            color=discord.Color.red()
        )
        embed.set_footer(text="Hãy thử lại sau hoặc mua thêm vé quay.")
        await ctx.send(embed=embed)
        return  # Dừng lệnh nếu không đủ điều kiện quay

    # Cơ chế tỷ lệ ngẫu nhiên
    rarity_chances = {
        "giải ba": 0.9,  # 70% cho thẻ thường
        "giải nhì": 0.01,    # 20% cho thẻ hiếm
        "giải nhất": 0.001  # 10% cho thẻ huyền thoại
    }

    # Chọn thẻ ngẫu nhiên theo tỷ lệ
    rarity = random.choices(
        list(rarity_chances.keys()), 
        weights=list(rarity_chances.values()), 
        k=1
    )[0]

    # Lọc các thẻ theo rarity
    available_cards = [card for card in cards if card["rarity"] == rarity]
    chosen_card = random.choice(available_cards)

    # Thêm thẻ vào kho của người chơi
    if ctx.author.id not in user_inventory:
        user_inventory[ctx.author.id] = []

    user_inventory[ctx.author.id].append(chosen_card)

    # Tạo embed để hiển thị thẻ với hình ảnh
    embed = discord.Embed(
        title="<a:xxx_canhtrai:1354516494708506897>  Bạn mở thẻ gacha! <a:xxx_canhphai:1354516607262789713>",
        description=f"<:prd_topvoice:1366435381729562734> Độ hiếm: {chosen_card['rarity']}\n"
                    f"<a:xxx_ga:1359903185849815080> Phần thưởng: {chosen_card['reward']}",
        color=discord.Color.green()
    )
    embed.set_thumbnail(url="https://i.imgur.com/ITXacnI.png")  # Thêm một biểu tượng may mắn
    embed.add_field(name="<:prd_topvoice:1366435381729562734>Độ hiếm", value=f"**{chosen_card['rarity']}**", inline=False)
    embed.add_field(name="<a:xxx_ga:1359903185849815080> Phần thưởng", value=f"**{chosen_card['reward']}**", inline=False)
    embed.set_image(url=chosen_card["image_url"])  # Thêm hình ảnh của thẻ

    # Gửi thông báo mở gacha với embed
    await ctx.send(embed=embed)

# Lệnh kiểm tra kho
@bot.command()
async def inventory(ctx):
    """Kiểm tra kho thẻ của người dùng."""
    if ctx.author.id not in user_inventory or not user_inventory[ctx.author.id]:
        await ctx.send("Kho của bạn hiện tại trống. Hãy mở gacha bằng lệnh `!gacha`!")
        return

    inventory_list = user_inventory[ctx.author.id]
    inventory_text = "Kho của bạn:\n"
    for card in inventory_list:
        inventory_text += f"- {card['name']} (Sức mạnh: {card['strength']})\n"
    
    await ctx.send(inventory_text)

# Lệnh giúp (help)
@bot.command()
async def help_command(ctx):
    """Hiển thị các lệnh bot."""
    embed = discord.Embed(
        title="Danh sách lệnh",
        description="Dưới đây là danh sách các lệnh có sẵn của bot",
        color=discord.Color.blue()
    )
    embed.add_field(name="!gacha", value="Mở gacha để nhận thẻ ngẫu nhiên.", inline=False)
    embed.add_field(name="!inventory", value="Kiểm tra kho thẻ của bạn", inline=False)
    embed.add_field(name="!add_admin", value="Cấp quyền admin cho người khác (chỉ admin chính)", inline=False)
    embed.add_field(name="!is_admin", value="Kiểm tra người chơi có phải admin hay không.", inline=False)
    embed.add_field(name="!add_luot_quay", value="Cấp thêm lượt quay cho người chơi (chỉ admin chính)", inline=False)
    await ctx.send(embed=embed)

# Cuối cùng, không được đặt trong bất kỳ hàm nào nữa
TOKEN = os.getenv("DISCORD_TOKEN")

