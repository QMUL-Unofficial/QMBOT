import discord
from discord.ext import commands
from bot.config import WELCOME_CHANNEL_ID

ROLE_COLOR_EMOJIS = {
    "🟥": "Red",
    "🟩": "Green",
    "🟦": "Blue",
    "🟨": "Yellow",
    "🟪": "Purple",
    "⬛": "Black",
}

ROLE_COLOUR_MSG_FILE = "role_colour_msg.txt"  # stored in working dir; ok

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="warn", help="Warn an individual for profanity")
    async def warn(self, ctx, member: discord.Member):
        if member == ctx.author:
            return await ctx.send("Putting yourself in timeout is not something you should be proud to say to the class")
        if member.bot:
            return await ctx.send("watch ur tone. twink")

        warnings = [
            "⚠️ Warning: That message has been escorted out by security.",
            "⚠️ Warning: Please keep your hands, feet, and words to yourself.",
            "⚠️ Warning: This is a no-weird-zone. Thank you for your cooperation.",
            "⚠️ Warning: Bonk. Go to respectful conversation jail.",
            "⚠️ Warning: That was a bit much. Let’s dial it back.",
            "⚠️ Warning: Socks will remain dry. Boundaries enforced.",
            "⚠️ Warning: International incidents are not permitted here."
        ]
        await ctx.send(f"{ctx.author.mention} warns {member.mention}:\n> {discord.utils.choice(warnings)}")

    @commands.command(name="rolecolour", help="Post a message where users can choose their color role.")
    @commands.has_permissions(manage_roles=True)
    async def rolecolour(self, ctx):
        desc = "\n".join([f"{emoji} = **{role}**" for emoji, role in ROLE_COLOR_EMOJIS.items()])
        embed = discord.Embed(title="🎨 Pick Your Colour!", description=desc, color=discord.Color.purple())
        msg = await ctx.send(embed=embed)
        for emoji in ROLE_COLOR_EMOJIS.keys():
            await msg.add_reaction(emoji)
        with open(ROLE_COLOUR_MSG_FILE, "w") as f:
            f.write(str(msg.id))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == (self.bot.user.id if self.bot.user else None):
            return

        try:
            with open(ROLE_COLOUR_MSG_FILE, "r") as f:
                target_msg_id = int(f.read())
        except Exception:
            return

        if payload.message_id != target_msg_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        role_name = ROLE_COLOR_EMOJIS.get(str(payload.emoji))
        if not role_name:
            return

        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            try:
                role = await guild.create_role(name=role_name, colour=discord.Colour.default())
            except discord.Forbidden:
                return

        # remove other colour roles
        for rname in ROLE_COLOR_EMOJIS.values():
            r = discord.utils.get(guild.roles, name=rname)
            if r and r in member.roles and r.name != role_name:
                await member.remove_roles(r)

        if role not in member.roles:
            await member.add_roles(role)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return
        embed = discord.Embed(
            title="Welcome to QMUL - Unofficial 🎓",
            description=f"{member.mention}, we're glad to have you here!",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.set_footer(text="Make sure to check out the channels and have fun!")
        await channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
