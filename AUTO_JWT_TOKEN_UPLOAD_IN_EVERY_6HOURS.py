import os
import subprocess
import sys
import json
import time
import asyncio
import aiohttp
import schedule
import threading
import requests
from datetime import datetime
from base64 import b64encode

# Auto-install required modules
def install_modules():
    required_modules = [
        "python-telegram-bot==21.4",  # Updated to v21.4 for Python 3.12 compatibility
        "aiohttp",
        "schedule",
        "requests"
    ]
    for module in required_modules:
        try:
            __import__(module.split("==")[0])
        except ImportError:
            print(f"Installing {module}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", module])
            except subprocess.CalledProcessError as e:
                print(f"Failed to install {module}: {e}")
                sys.exit(1)

install_modules()

# Telegram imports
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

# ======= CONFIG ========
TOKEN = "8380344221:AAFZ-Dnj6xeQuyjjUD5Yb_7uqDg4ios2vjE"
API_URL = "https://anixhjwt.vercel.app/token"
CHANNEL_URL = "https://t.me/+M0OaMKjzvKVjZGRk"
ADMIN_ID = itz_veltrixx
MAX_CONCURRENT = 10

# GitHub Configuration
GITHUB_TOKEN = "अपने_GitHUB_का_एक्सेस_टोकन_यहां_डालो"
GITHUB_REPO_NAME = "अपने_रिपोस्टोरी_का_नाम_यहां_पे_डालो" #ऐसा डालना है एक्साम्प्ल देख लो username/repo_name
GITHUB_FILE_NAME = "token_ind.json"
GITHUB_API_URL = "https://api.github.com"

# Auto-generation configuration
AUTO_GENERATE_INTERVAL_HOURS = 6
current_accounts_file = None
# =======================

join_button = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔗 Join Channel", url=CHANNEL_URL)]]
)

# ============= ADMIN CHECK FUNCTION =============
def is_admin(user_id):
    """Check if user is admin"""
    return user_id == ADMIN_ID

# ============= GITHUB FUNCTIONS (USING DIRECT API) =============
def github_update_file(region_map):
    """
    Update token_ind.json in GitHub repo (Direct API calls)
    """
    try:
        # Merge all region tokens
        all_tokens = []
        for region, tokens in region_map.items():
            if isinstance(tokens, list):
                all_tokens.extend(tokens)
        
        if not all_tokens:
            return "❌ No valid tokens found, GitHub update skipped"
        
        # Prepare new file content
        new_content = json.dumps(all_tokens, indent=2, ensure_ascii=False)
        
        # GitHub API headers
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Get file SHA (if exists)
        file_url = f"{GITHUB_API_URL}/repos/{GITHUB_REPO_NAME}/contents/{GITHUB_FILE_NAME}"
        response = requests.get(file_url, headers=headers)
        
        if response.status_code == 200:
            # File exists, update it
            file_data = response.json()
            sha = file_data["sha"]
            
            update_data = {
                "message": f"🤖 Auto-update by JWT Bot | {len(all_tokens)} tokens | {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "content": b64encode(new_content.encode()).decode(),
                "sha": sha
            }
            
            response = requests.put(file_url, headers=headers, json=update_data)
            
            if response.status_code == 200:
                return f"✅ GitHub Update Successful! {len(all_tokens)} tokens updated in {GITHUB_FILE_NAME}"
            else:
                return f"❌ GitHub Update Failed: {response.status_code} - {response.text}"
                
        elif response.status_code == 404:
            # File doesn't exist, create new
            create_data = {
                "message": f"🤖 Initial create by JWT Bot | {len(all_tokens)} tokens | {time.strftime('%Y-%m-%d %H:%M:%S')}",
                "content": b64encode(new_content.encode()).decode()
            }
            
            response = requests.put(file_url, headers=headers, json=create_data)
            
            if response.status_code == 201:
                return f"✅ New GitHub File Created! {len(all_tokens)} tokens added to {GITHUB_FILE_NAME}"
            else:
                return f"❌ GitHub Create Failed: {response.status_code} - {response.text}"
        else:
            return f"❌ GitHub API Error: {response.status_code} - {response.text}"
                
    except Exception as e:
        return f"❌ GitHub Update Failed: {str(e)}"

async def async_github_update(region_map):
    """Async wrapper for GitHub update"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, github_update_file, region_map)
    return result

# ============= AUTO GENERATION SCHEDULER =============
def start_scheduler(app):
    """Start the auto-generation scheduler"""
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1 minute check interval
    
    # Schedule auto-generation every 6 hours
    schedule.every(AUTO_GENERATE_INTERVAL_HOURS).hours.do(
        lambda: asyncio.run(auto_generate_tokens(app))
    )
    
    # Start scheduler thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    print(f"🔄 Auto-generation scheduler started! Running every {AUTO_GENERATE_INTERVAL_HOURS} hours")

async def auto_generate_tokens(app):
    """Auto token generation and GitHub update"""
    if not current_accounts_file:
        print("ℹ️ No accounts file set for auto-generation")
        return
    
    try:
        print("🔄 Starting auto token generation...")
        
        # Notify admin
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔄 **Auto Token Generation Started!**\n"
                 f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                 f"📁 Using file: {os.path.basename(current_accounts_file) if current_accounts_file else 'N/A'}"
        )
        
        # Read file
        with open(current_accounts_file, "r", encoding="utf-8") as f:
            accounts = json.load(f)
        
        # Generate tokens
        results = await generate_tokens_from_accounts(accounts)
        
        # Create region map
        region_map = {}
        for r in results:
            if r and r.get("token"):
                region = r.get("region", "UNKNOWN")
                if region not in region_map:
                    region_map[region] = []
                region_map[region].append({"uid": r["uid"], "token": r["token"]})
        
        # GitHub update
        github_result = await async_github_update(region_map)
        
        # Send final result to admin
        success = sum(1 for r in results if r and r.get("token"))
        fail = len(accounts) - success
        
        await app.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ **Auto Generation Complete!**\n"
                 f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                 f"✅ Success: {success}\n"
                 f"❌ Failed: {fail}\n"
                 f"🔗 GitHub: {github_result}\n"
                 f"⏳ Next auto-generation in {AUTO_GENERATE_INTERVAL_HOURS} hours"
        )
        
        print("✅ Auto token generation completed!")
        
    except Exception as e:
        error_msg = f"❌ Auto generation failed: {str(e)}"
        print(error_msg)
        try:
            await app.bot.send_message(chat_id=ADMIN_ID, text=error_msg)
        except:
            pass

async def generate_tokens_from_accounts(accounts):
    """Generate tokens from accounts list"""
    results = []
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    async with aiohttp.ClientSession() as session:
        async def process_account(account):
            uid = account.get("uid")
            pwd = account.get("password") or account.get("pass") or account.get("pwd")
            
            if not uid or not pwd:
                return {"uid": uid or "missing", "token": None, "region": "UNKNOWN", "raw": {"error": "missing uid/password"}}
            
            async with semaphore:
                try:
                    result = await generate_token(session, str(uid), str(pwd))
                    return result
                except Exception as e:
                    return {"uid": uid, "token": None, "region": "UNKNOWN", "raw": {"error": str(e)}}
        
        # Process all accounts
        tasks = [process_account(acc) for acc in accounts]
        results = await asyncio.gather(*tasks)
    
    return results

# ============= START COMMAND =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ **Access Denied!**\nThis bot is for admin use only.")
        return

    name = update.effective_user.first_name or "Admin"
    
    welcome_text = (
        f"👋 Welcome {name}!\n\n"
        f"🤖 **Admin JWT Token Bot**\n\n"
        f"🔧 **Features:**\n"
        f"• Send .json file to generate tokens\n"
        f"• Auto GitHub updates\n"
        f"• 🕒 **Auto-generation every {AUTO_GENERATE_INTERVAL_HOURS} hours**\n"
        f"• Live notifications\n\n"
        f"📁 **Send JSON format:**\n"
        "[\n  {\"uid\": \"4154503773\", \"password\": \"ues9li9Vx2\"},\n  ...\n]"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=join_button)

# ============= TOKEN GENERATOR =============
async def generate_token(session: aiohttp.ClientSession, uid: str, password: str):
    """
    Calls API_URL?uid=...&password=...
    Returns dict: {"uid": uid, "token": token_or_None, "region": region, "raw": data}
    """
    params = {"uid": uid, "password": password}
    try:
        async with session.get(API_URL, params=params, timeout=10) as resp:
            data = await resp.json(content_type=None)

            token_raw = data.get("token") or data.get("access_token") or None
            if token_raw and isinstance(token_raw, str):
                if token_raw.strip().lower().startswith("bearer "):
                    token_clean = token_raw.strip()[7:]
                else:
                    token_clean = token_raw.strip()
            else:
                token_clean = None

            # Region info (ipRegion or notiRegion)
            region = data.get("notiRegion") or data.get("ipRegion") or "UNKNOWN"

            return {"uid": uid, "token": token_clean, "region": region, "raw": data}
    except asyncio.TimeoutError:
        return {"uid": uid, "token": None, "region": "UNKNOWN", "raw": {"error": "timeout"}}
    except Exception as e:
        return {"uid": uid, "token": None, "region": "UNKNOWN", "raw": {"error": str(e)}}

# ============= JSON FILE HANDLER =============
async def handle_json_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin check
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ **Access Denied!**\nThis bot is for admin use only.")
        return

    doc = update.message.document
    if not doc.file_name.endswith(".json"):
        await update.message.reply_text("❗ Please send a .json file only.", reply_markup=join_button)
        return

    file = await doc.get_file()
    file_path = await file.download_to_drive()

    # Store current file for auto-generation
    global current_accounts_file
    current_accounts_file = file_path

    # Parse JSON
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            accounts = json.load(f)
        if not isinstance(accounts, list):
            raise ValueError("JSON must be a list of objects with 'uid' and 'password'")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to read JSON: {e}", reply_markup=join_button)
        return

    total = len(accounts)
    if total == 0:
        await update.message.reply_text("❗ JSON list is empty.", reply_markup=join_button)
        return

    # Live notification start
    await update.message.reply_text(
        f"📂 **New File Received!**\n"
        f"• Total IDs: {total}\n"
        f"• ⚙️ Token generation started...\n"
        f"• 🔄 GitHub update enabled\n"
        f"• 🕒 This file will be used for auto-generation every {AUTO_GENERATE_INTERVAL_HOURS} hours",
        reply_markup=join_button
    )
    
    status_msg = await update.message.reply_text("🔄 Initializing...")

    results = [None] * total
    start_time = time.time()
    prev_text = ""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async def update_time():
        nonlocal prev_text
        while any(r is None for r in results):
            generated_results = [r for r in results if r is not None]
            generated = len(generated_results)
            elapsed = int(time.time() - start_time)
            avg = elapsed / generated if generated else 0
            remaining = int(avg * (total - generated)) if generated else "..."

            new_text = (
                f"🟢 **GENERATION IN PROGRESS**\n"
                f"• Progress: {generated}/{total}\n"
                f"• Time elapsed: {elapsed}s\n"
                f"• ⏳ Estimated remaining: {remaining}s\n"
                f"• 🔗 GitHub update pending..."
            )
            if new_text != prev_text:
                prev_text = new_text
                try:
                    await status_msg.edit_text(new_text, reply_markup=join_button)
                except Exception:
                    pass
            await asyncio.sleep(1)

    async with aiohttp.ClientSession() as session:
        async def task_wrapper(i, account):
            uid = account.get("uid")
            pwd = account.get("password") or account.get("pass") or account.get("pwd")
            if not uid or not pwd:
                results[i] = {"uid": uid or "missing", "token": None, "region": "UNKNOWN", "raw": {"error": "missing uid/password"}}
                return
            async with semaphore:
                try:
                    st = time.time()
                    result = await generate_token(session, str(uid), str(pwd))
                    result["time"] = int(time.time() - st)
                    results[i] = result
                except Exception as e:
                    results[i] = {"uid": uid, "token": None, "region": "UNKNOWN", "time": 0, "raw": {"error": str(e)}}

        tasks = [task_wrapper(i, acc) for i, acc in enumerate(accounts)]
        await asyncio.gather(update_time(), *tasks)

    # === REGION-WISE FILES ===
    region_map = {}
    for r in results:
        if r and r.get("token"):
            region = r.get("region", "UNKNOWN")
            if region not in region_map:
                region_map[region] = []
            region_map[region].append({"uid": r["uid"], "token": r["token"]})

    # Write and send each region file with renamed outputs
    for region, tokens in region_map.items():
        # Rename files as per requirement
        if region == "IND":
            out_fname = "token_ind.json"
        elif region == "NA":
            out_fname = "token_na.json"
        else:
            out_fname = f"{region}_tokens.json"
        
        try:
            with open(out_fname, "w", encoding="utf-8") as out_file:
                json.dump(tokens, out_file, indent=2, ensure_ascii=False)
            await update.message.reply_document(
                document=open(out_fname, "rb"),
                filename=out_fname,
                caption=f"✅ {len(tokens)} tokens generated for region `{region}`",
                parse_mode="Markdown",
                reply_markup=join_button
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Failed to send {region} file: {e}")

    # === GITHUB UPDATE ===
    github_status_msg = await update.message.reply_text("🔄 Updating GitHub repository...")
    
    # GitHub update
    github_result = await async_github_update(region_map)
    
    await github_status_msg.edit_text(github_result)

    # Final status with auto-generation info
    success = sum(1 for r in results if r and r.get("token"))
    fail = total - success
    
    final_msg = (
        f"🎉 **Generation Complete!**\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {fail}\n"
        f"🔗 {github_result}\n\n"
        f"🕒 **Auto-generation Activated!**\n"
        f"This file will be used for auto-generation every {AUTO_GENERATE_INTERVAL_HOURS} hours.\n"
        f"Next auto-generation: {AUTO_GENERATE_INTERVAL_HOURS} hours from now."
    )
    
    await update.message.reply_text(final_msg, reply_markup=join_button)

# ============= ADMIN COMMANDS =============
async def admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    commands_text = (
        "👨‍💻 **Admin Commands:**\n\n"
        "📁 Send .json file - Generate tokens and set for auto-generation\n"
        "⏰ /status - Check auto-generation status\n"
        "🔄 /force_update - Force immediate auto-generation\n"
        "❌ /clear_file - Clear current auto-generation file"
    )
    
    await update.message.reply_text(commands_text)

async def check_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    status_text = (
        f"🤖 **Bot Status**\n\n"
        f"📁 Current file: {current_accounts_file or 'Not set'}\n"
        f"🕒 Auto-generation interval: {AUTO_GENERATE_INTERVAL_HOURS} hours\n"
        f"🔧 Next auto-generation: {AUTO_GENERATE_INTERVAL_HOURS} hours from last run\n"
        f"⏰ Server time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await update.message.reply_text(status_text)

async def force_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if not current_accounts_file:
        await update.message.reply_text("❌ No file set for auto-generation!")
        return

    await update.message.reply_text("🔄 Force update started...")
    await auto_generate_tokens(context.application)

async def clear_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    global current_accounts_file
    current_accounts_file = None
    await update.message.reply_text("✅ Auto-generation file cleared!")

# ============= MAIN =============
if __name__ == "__main__":
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", check_status))
    app.add_handler(CommandHandler("force_update", force_update))
    app.add_handler(CommandHandler("clear_file", clear_file))
    app.add_handler(CommandHandler("admin", admin_commands))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_json_file))
    
    # Start scheduler
    start_scheduler(app)
    
    print("🤖 Admin JWT Bot is running...")
    print(f"🔒 Restricted to Admin ID: {ADMIN_ID}")
    print(f"🕒 Auto-generation: Every {AUTO_GENERATE_INTERVAL_HOURS} hours")
    print("🔗 GitHub Auto-Update Feature: ENABLED")
    
    app.run_polling()