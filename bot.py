import os
import logging
import json
import string
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

# ==================== CONFIGURATION ====================
TOKEN = "8799466936:AAFdnvH_2k9vNayz6jKlSREo_nyyhaI_cUg"
OWNER_ID = 8633573748
DATA_FILE = "file_manager_data.json"
MAX_FILE_SIZE = 100 * 1024 * 1024
ALLOWED_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', 
                     '.zip', '.rar', '.7z', '.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3',
                     '.json', '.xml', '.csv', '.py', '.js', '.html', '.css']

# Conversation states
FILE_STATE, DESC_STATE, CAT_STATE, CAT_NAME_STATE, CAPTION_STATE = range(5)

# ==================== DATA MANAGER ====================
class FileManagerData:
    def __init__(self):
        self.files = {}
        self.categories = {}
        self.users = {}
        self.load_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.files = data.get('files', {})
                    self.categories = data.get('categories', {})
                    self.users = data.get('users', {})
            except:
                pass

    def save_data(self):
        try:
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump({
                    'files': self.files,
                    'categories': self.categories,
                    'users': self.users
                }, f, ensure_ascii=False, indent=2)
        except:
            pass

    def generate_key(self):
        chars = string.ascii_uppercase + string.digits
        while True:
            key = ''.join(random.choices(chars, k=8))
            if key not in self.files:
                return key

    def add_file(self, file_id, file_name, description, category, file_size, mime_type, caption=""):
        key = self.generate_key()
        self.files[key] = {
            'key': key,
            'file_id': file_id,
            'file_name': file_name,
            'description': description,
            'category': category,
            'file_size': file_size,
            'mime_type': mime_type,
            'uploaded_at': datetime.now().isoformat(),
            'download_count': 0,
            'caption': caption,
            'is_active': True
        }
        if category not in self.categories:
            self.categories[category] = []
        self.categories[category].append(key)
        self.save_data()
        return key

    def get_file(self, key):
        return self.files.get(key) if key in self.files and self.files[key].get('is_active', True) else None

    def delete_file(self, key):
        if key in self.files:
            category = self.files[key].get('category')
            if category and category in self.categories:
                if key in self.categories[category]:
                    self.categories[category].remove(key)
                if not self.categories[category]:
                    del self.categories[category]
            del self.files[key]
            self.save_data()
            return True
        return False

    def get_files_by_category(self, category):
        keys = self.categories.get(category, [])
        return [self.files[k] for k in keys if k in self.files]

    def get_all_categories(self):
        return list(self.categories.keys())

    def search_by_key(self, key):
        return self.files.get(key) if key in self.files and self.files[key].get('is_active', True) else None

    def get_owner_stats(self):
        total_files = len([f for f in self.files.values() if f.get('is_active', True)])
        total_downloads = sum([f.get('download_count', 0) for f in self.files.values() if f.get('is_active', True)])
        return {
            'total_files': total_files,
            'total_downloads': total_downloads,
            'total_users': len(self.users),
            'total_categories': len(self.categories)
        }

# ==================== BOT ====================
class FileManagerBot:
    def __init__(self):
        self.data = FileManagerData()
        self.application = None

    def is_owner(self, user_id):
        return user_id == OWNER_ID

    @staticmethod
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    # ==================== START ====================
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        if user_id not in self.data.users:
            self.data.users[user_id] = {
                'username': user.username or user.first_name,
                'first_seen': datetime.now().isoformat()
            }
            self.data.save_data()
        
        if self.is_owner(user_id):
            await self.owner_menu(update)
        else:
            await self.user_menu(update)

    async def owner_menu(self, update: Update):
        stats = self.data.get_owner_stats()
        text = f"""
👑 *Owner Panel*

📊 *Statistics:*
• 📁 Files: {stats['total_files']}
• 📂 Categories: {stats['total_categories']}
• 👥 Users: {stats['total_users']}
• 📥 Downloads: {stats['total_downloads']}

🔧 *Choose an option:*
"""
        keyboard = [
            [InlineKeyboardButton("➕ Add File", callback_data="add_file")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("📂 Manage Files", callback_data="manage")],
            [InlineKeyboardButton("👥 Users", callback_data="users")],
            [InlineKeyboardButton("📁 Browse", callback_data="browse")],
            [InlineKeyboardButton("🔑 Search", callback_data="search")],
        ]
        
        if update.message:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def user_menu(self, update: Update):
        text = f"""
📁 *File Manager*

Welcome {escape_markdown(update.effective_user.first_name)}!

🔍 *Choose an option:*
"""
        keyboard = [
            [InlineKeyboardButton("📁 Browse", callback_data="browse")],
            [InlineKeyboardButton("🔑 Search", callback_data="search")],
        ]
        
        if update.message:
            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== BUTTON HANDLER ====================
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data

        if data == "main":
            if self.is_owner(user_id):
                await self.owner_menu(update)
            else:
                await self.user_menu(update)
        
        elif data == "browse":
            await self.show_categories(query)
        
        elif data == "search":
            await query.edit_message_text(
                "🔑 *Search by Key*\n\nSend me the 8-digit file key:",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['search_mode'] = True
        
        elif data == "add_file":
            if self.is_owner(user_id):
                # Start upload process directly
                context.user_data['upload_state'] = FILE_STATE
                await query.edit_message_text(
                    "📤 *Add File*\n\nSend me the file to upload.\n\nSupported: PDF, DOC, ZIP, JPG, MP4, PY, etc.\nMax: 100MB\n\nType /cancel to cancel.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text("❌ Only owner can add files!", parse_mode=ParseMode.MARKDOWN)
        
        elif data == "broadcast":
            if self.is_owner(user_id):
                await self.start_broadcast(query, context)
            else:
                await query.edit_message_text("❌ Only owner can broadcast!", parse_mode=ParseMode.MARKDOWN)
        
        elif data == "manage":
            if self.is_owner(user_id):
                await self.manage_files(query)
            else:
                await query.edit_message_text("❌ Only owner can manage!", parse_mode=ParseMode.MARKDOWN)
        
        elif data == "users":
            if self.is_owner(user_id):
                await self.show_users(query)
            else:
                await query.edit_message_text("❌ Only owner can view!", parse_mode=ParseMode.MARKDOWN)
        
        elif data.startswith("category_"):
            category = data.replace("category_", "")
            await self.show_category_files(query, category)
        
        elif data.startswith("file_"):
            key = data.replace("file_", "")
            await self.show_file_details(query, key, user_id)
        
        elif data.startswith("download_"):
            key = data.replace("download_", "")
            await self.download_file(query, key, user_id)
        
        elif data.startswith("delete_"):
            if self.is_owner(user_id):
                key = data.replace("delete_", "")
                await self.delete_file(query, key)
        
        elif data.startswith("page_"):
            _, category, page = data.split("_")
            await self.show_category_files(query, category, int(page))
        
        elif data in ["broadcast_confirm", "broadcast_cancel"]:
            await self.handle_broadcast_confirm(query, context)
        
        elif data.startswith("upload_cat_"):
            # This handles the category selection from the upload process
            await self.handle_category_selection(query, context)

    # ==================== UPLOAD HANDLER ====================
    async def handle_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all upload steps"""
        user_id = update.effective_user.id
        
        if not self.is_owner(user_id):
            await update.message.reply_text("❌ Only owner can upload!", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        
        state = context.user_data.get('upload_state', -1)
        
        # STATE: Waiting for file
        if state == FILE_STATE:
            if not update.message.document:
                await update.message.reply_text("⚠️ Please send a file!", parse_mode=ParseMode.MARKDOWN)
                return FILE_STATE
            
            doc = update.message.document
            
            if doc.file_size > MAX_FILE_SIZE:
                await update.message.reply_text(f"❌ File too large! Max: {self.format_size(MAX_FILE_SIZE)}", parse_mode=ParseMode.MARKDOWN)
                return FILE_STATE
            
            ext = os.path.splitext(doc.file_name or "")[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                await update.message.reply_text(f"❌ Unsupported file type: {ext}", parse_mode=ParseMode.MARKDOWN)
                return FILE_STATE
            
            context.user_data['file_id'] = doc.file_id
            context.user_data['file_name'] = doc.file_name
            context.user_data['file_size'] = doc.file_size
            context.user_data['mime_type'] = doc.mime_type
            context.user_data['upload_state'] = DESC_STATE
            
            await update.message.reply_text(
                f"✅ File received: {escape_markdown(doc.file_name)}\n📊 {self.format_size(doc.file_size)}\n\n📝 Send description:",
                parse_mode=ParseMode.MARKDOWN
            )
            return DESC_STATE
        
        # STATE: Waiting for description
        elif state == DESC_STATE:
            desc = update.message.text
            if len(desc) > 500:
                await update.message.reply_text("⚠️ Description too long! (max 500 chars)", parse_mode=ParseMode.MARKDOWN)
                return DESC_STATE
            
            context.user_data['description'] = desc
            context.user_data['upload_state'] = CAT_STATE
            
            # Show categories
            categories = self.data.get_all_categories()
            keyboard = []
            for cat in categories:
                keyboard.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"upload_cat_{cat}")])
            keyboard.append([InlineKeyboardButton("➕ New Category", callback_data="upload_cat_new")])
            keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="main")])
            
            await update.message.reply_text(
                "📂 *Select Category*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CAT_STATE
        
        # STATE: New category name
        elif state == CAT_NAME_STATE:
            category = update.message.text.strip()
            if not category or len(category) > 50:
                await update.message.reply_text("⚠️ Enter valid category name (1-50 chars):", parse_mode=ParseMode.MARKDOWN)
                return CAT_NAME_STATE
            
            context.user_data['category'] = category
            context.user_data['upload_state'] = CAPTION_STATE
            
            await update.message.reply_text(
                f"✅ Category: {escape_markdown(category)}\n\n💬 Send caption or /skip:",
                parse_mode=ParseMode.MARKDOWN
            )
            return CAPTION_STATE
        
        # STATE: Waiting for caption
        elif state == CAPTION_STATE:
            caption = "" if update.message.text == "/skip" else update.message.text
            
            # Save file
            file_id = context.user_data.get('file_id')
            file_name = context.user_data.get('file_name')
            file_size = context.user_data.get('file_size')
            mime_type = context.user_data.get('mime_type')
            description = context.user_data.get('description')
            category = context.user_data.get('category')
            
            if not all([file_id, file_name, description, category]):
                await update.message.reply_text("❌ Upload data missing! Start over.", parse_mode=ParseMode.MARKDOWN)
                return ConversationHandler.END
            
            key = self.data.add_file(
                file_id=file_id,
                file_name=file_name,
                description=description,
                category=category,
                file_size=file_size,
                mime_type=mime_type,
                caption=caption
            )
            
            # Clear upload data
            context.user_data.clear()
            
            await update.message.reply_text(
                f"✅ *File Uploaded!*\n\n"
                f"📄 {escape_markdown(file_name)}\n"
                f"🔑 *Key:* `{key}`\n"
                f"📂 {escape_markdown(category)}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"🔑 *SAVE THIS KEY:* `{key}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Users can search with this key.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📄 View", callback_data=f"file_{key}")],
                    [InlineKeyboardButton("➕ Add More", callback_data="add_file")],
                    [InlineKeyboardButton("🔙 Main", callback_data="main")]
                ])
            )
            return ConversationHandler.END
        
        return ConversationHandler.END

    # ==================== CATEGORY SELECTION ====================
    async def handle_category_selection(self, query, context):
        """Handle category selection from callback"""
        # query is already a CallbackQuery object from the button_handler
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Access denied!", parse_mode=ParseMode.MARKDOWN)
            return
        
        data = query.data
        
        if data == "upload_cat_new":
            await query.edit_message_text(
                "✏️ *New Category*\n\nType the category name:",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['upload_state'] = CAT_NAME_STATE
        
        elif data.startswith("upload_cat_"):
            category = data.replace("upload_cat_", "")
            context.user_data['category'] = category
            context.user_data['upload_state'] = CAPTION_STATE
            
            await query.edit_message_text(
                f"✅ Category: {escape_markdown(category)}\n\n💬 Send caption or /skip:",
                parse_mode=ParseMode.MARKDOWN
            )

    # ==================== SEARCH ====================
    async def handle_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle search by key"""
        if not context.user_data.get('search_mode'):
            return
        
        key = update.message.text.strip().upper()
        key = ''.join(c for c in key if c.isalnum())
        
        if len(key) != 8:
            await update.message.reply_text("❌ Invalid key! Must be 8 characters.", parse_mode=ParseMode.MARKDOWN)
            return
        
        file_info = self.data.search_by_key(key)
        
        if not file_info:
            await update.message.reply_text(
                f"❌ No file found with key: `{key}`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 Search Again", callback_data="search")],
                    [InlineKeyboardButton("🔙 Main", callback_data="main")]
                ])
            )
            context.user_data['search_mode'] = False
            return
        
        user_id = update.effective_user.id
        await self.show_file_details_from_message(update, key, user_id)
        context.user_data['search_mode'] = False

    # ==================== SHOW FILE DETAILS ====================
    async def show_file_details(self, query, key, user_id):
        file_info = self.data.get_file(key)
        if not file_info:
            await query.edit_message_text("❌ File not found!", parse_mode=ParseMode.MARKDOWN)
            return
        
        text = f"""
📄 *{escape_markdown(file_info['file_name'])}*

🔑 Key: `{file_info['key']}`
📂 {escape_markdown(file_info['category'])}
📝 {escape_markdown(file_info.get('description', 'No description'))}
📊 {self.format_size(file_info['file_size'])}
📥 {file_info['download_count']} downloads
📅 {file_info['uploaded_at'][:10]}
"""
        
        keyboard = [[InlineKeyboardButton("📥 Download", callback_data=f"download_{key}")]]
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="browse")])
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_file_details_from_message(self, update, key, user_id):
        file_info = self.data.get_file(key)
        if not file_info:
            await update.message.reply_text("❌ File not found!", parse_mode=ParseMode.MARKDOWN)
            return
        
        text = f"""
🔑 *File Found!*

📄 {escape_markdown(file_info['file_name'])}
🔑 Key: `{file_info['key']}`
📂 {escape_markdown(file_info['category'])}
📝 {escape_markdown(file_info.get('description', 'No description'))}
📊 {self.format_size(file_info['file_size'])}
📥 {file_info['download_count']} downloads
"""
        
        keyboard = [[InlineKeyboardButton("📥 Download", callback_data=f"download_{key}")]]
        if self.is_owner(user_id):
            keyboard.append([InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 Main", callback_data="main")])
        
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== DOWNLOAD ====================
    async def download_file(self, query, key, user_id):
        file_info = self.data.get_file(key)
        if not file_info:
            await query.edit_message_text("❌ File not found!", parse_mode=ParseMode.MARKDOWN)
            return
        
        try:
            await query.message.reply_document(
                document=file_info['file_id'],
                caption=f"📄 {escape_markdown(file_info['file_name'])}\n🔑 `{file_info['key']}`"
            )
            # Update download count
            file_info['download_count'] += 1
            self.data.save_data()
            
            await query.edit_message_text(
                f"✅ File sent!\n\n📄 {escape_markdown(file_info['file_name'])}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="browse")]])
            )
        except Exception as e:
            logging.error(f"Download error: {e}")
            await query.edit_message_text("❌ Error downloading!", parse_mode=ParseMode.MARKDOWN)

    # ==================== DELETE ====================
    async def delete_file(self, query, key):
        if self.data.delete_file(key):
            await query.edit_message_text(
                "✅ File deleted!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="manage")]])
            )
        else:
            await query.edit_message_text("❌ Error deleting!", parse_mode=ParseMode.MARKDOWN)

    # ==================== BROWSE ====================
    async def show_categories(self, query):
        categories = self.data.get_all_categories()
        
        if not categories:
            await query.edit_message_text(
                "📂 No files available!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]])
            )
            return
        
        keyboard = []
        for cat in categories:
            count = len(self.data.categories[cat])
            keyboard.append([InlineKeyboardButton(f"📁 {cat} ({count})", callback_data=f"category_{cat}")])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main")])
        await query.edit_message_text("📂 *Categories*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_category_files(self, query, category, page=0):
        files = self.data.get_files_by_category(category)
        per_page = 5
        total = (len(files) + per_page - 1) // per_page
        
        if not files:
            await query.edit_message_text(f"📁 *{category}*\n\nNo files!", parse_mode=ParseMode.MARKDOWN)
            return
        
        start = page * per_page
        end = min(start + per_page, len(files))
        
        text = f"📁 *{category}*\n\n"
        for f in files[start:end]:
            text += f"📄 {escape_markdown(f['file_name'])}\n🔑 `{f['key']}`\n📥 {f['download_count']}\n\n"
        
        keyboard = []
        for f in files[start:end]:
            keyboard.append([InlineKeyboardButton(f"📄 {f['file_name'][:20]}", callback_data=f"file_{f['key']}")])
        
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("⬅️", callback_data=f"page_{category}_{page-1}"))
        if page < total - 1:
            nav.append(InlineKeyboardButton("➡️", callback_data=f"page_{category}_{page+1}"))
        if nav:
            nav.append(InlineKeyboardButton(f"{page+1}/{total}", callback_data="noop"))
            keyboard.append(nav)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="browse")])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== MANAGE ====================
    async def manage_files(self, query):
        files = [f for f in self.data.files.values() if f.get('is_active', True)]
        
        if not files:
            await query.edit_message_text(
                "📂 No files to manage!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Add", callback_data="add_file")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main")]
                ])
            )
            return
        
        keyboard = []
        for f in files[:20]:
            keyboard.append([InlineKeyboardButton(
                f"📄 {f['file_name'][:20]} ({f['key']})",
                callback_data=f"file_{f['key']}"
            )])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main")])
        await query.edit_message_text("🗑️ *Manage Files*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== USERS ====================
    async def show_users(self, query):
        users = self.data.users
        if not users:
            await query.edit_message_text("👥 No users!", parse_mode=ParseMode.MARKDOWN)
            return
        
        text = f"👥 *Users* ({len(users)})\n\n"
        for i, (uid, info) in enumerate(list(users.items())[:10], 1):
            text += f"{i}. {escape_markdown(info.get('username', f'User {uid}'))}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== BROADCAST ====================
    async def start_broadcast(self, query, context):
        await query.edit_message_text(
            "📢 *Broadcast*\n\nSend message to broadcast:\nType /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['broadcast'] = True

    async def handle_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.user_data.get('broadcast'):
            return
        
        if not self.is_owner(update.effective_user.id):
            await update.message.reply_text("❌ Only owner can broadcast!", parse_mode=ParseMode.MARKDOWN)
            context.user_data['broadcast'] = False
            return
        
        users = list(self.data.users.keys())
        if not users:
            await update.message.reply_text("❌ No users!", parse_mode=ParseMode.MARKDOWN)
            context.user_data['broadcast'] = False
            return
        
        context.user_data['broadcast_msg'] = update.message
        context.user_data['broadcast_users'] = users
        
        await update.message.reply_text(
            f"📢 Send to {len(users)} users?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Yes", callback_data="broadcast_confirm")],
                [InlineKeyboardButton("❌ No", callback_data="broadcast_cancel")]
            ])
        )

    async def handle_broadcast_confirm(self, query, context):
        if query.data == "broadcast_confirm":
            msg = context.user_data.get('broadcast_msg')
            users = context.user_data.get('broadcast_users', [])
            
            if not msg or not users:
                await query.edit_message_text("❌ Error!", parse_mode=ParseMode.MARKDOWN)
                return
            
            success = 0
            for uid in users:
                try:
                    await msg.copy(uid)
                    success += 1
                except:
                    pass
            
            await query.edit_message_text(
                f"✅ Sent to {success}/{len(users)} users!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]])
            )
            
            context.user_data['broadcast'] = False
            if 'broadcast_msg' in context.user_data:
                del context.user_data['broadcast_msg']
            if 'broadcast_users' in context.user_data:
                del context.user_data['broadcast_users']
        
        else:
            await query.edit_message_text(
                "❌ Cancelled!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main")]])
            )
            context.user_data['broadcast'] = False

    # ==================== CANCEL ====================
    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text(
            "❌ Cancelled!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main", callback_data="main")]])
        )
        return ConversationHandler.END

    # ==================== SETUP ====================
    def setup_application(self):
        """Setup the application"""
        self.application = Application.builder().token(TOKEN).build()
        
        # Add conversation handler for upload
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.add_file_callback, pattern="^add_file$"),
            ],
            states={
                FILE_STATE: [
                    MessageHandler(filters.Document.ALL, self.handle_upload),
                ],
                DESC_STATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_upload),
                ],
                CAT_STATE: [
                    CallbackQueryHandler(self.category_callback, pattern="^upload_cat_"),
                ],
                CAT_NAME_STATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_upload),
                ],
                CAPTION_STATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_upload),
                    CommandHandler("skip", self.handle_upload),
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.cancel),
                CallbackQueryHandler(self.cancel_callback, pattern="^main$"),
            ],
        )
        self.application.add_handler(conv_handler)
        
        # Search handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_search))
        
        # Broadcast conversation
        broadcast_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_broadcast, pattern="^broadcast$")],
            states={
                0: [MessageHandler(filters.ALL, self.handle_broadcast)],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        self.application.add_handler(broadcast_conv)
        
        # Main button handler for all other callbacks
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("cancel", self.cancel))

    async def add_file_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle add_file callback - This starts the upload process"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Only owner can add files!", parse_mode=ParseMode.MARKDOWN)
            return ConversationHandler.END
        
        await query.edit_message_text(
            "📤 *Add File*\n\nSend me the file to upload.\n\nSupported: PDF, DOC, ZIP, JPG, MP4, PY, etc.\nMax: 100MB\n\nType /cancel to cancel.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['upload_state'] = FILE_STATE
        return FILE_STATE

    async def category_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle category selection callback from the conversation"""
        query = update.callback_query
        await query.answer()
        
        if not self.is_owner(query.from_user.id):
            await query.edit_message_text("❌ Access denied!", parse_mode=ParseMode.MARKDOWN)
            return
        
        data = query.data
        
        if data == "upload_cat_new":
            await query.edit_message_text(
                "✏️ *New Category*\n\nType the category name:",
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data['upload_state'] = CAT_NAME_STATE
            return CAT_NAME_STATE
        
        elif data.startswith("upload_cat_"):
            category = data.replace("upload_cat_", "")
            context.user_data['category'] = category
            context.user_data['upload_state'] = CAPTION_STATE
            
            await query.edit_message_text(
                f"✅ Category: {escape_markdown(category)}\n\n💬 Send caption or /skip:",
                parse_mode=ParseMode.MARKDOWN
            )
            return CAPTION_STATE

    async def cancel_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel via callback"""
        query = update.callback_query
        await query.answer()
        context.user_data.clear()
        
        if self.is_owner(query.from_user.id):
            await self.owner_menu(update)
        else:
            await self.user_menu(update)
        return ConversationHandler.END

    # ==================== RUN ====================
    def run(self):
        self.setup_application()
        logging.info("Bot starting...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

# ==================== MAIN ====================
def main():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    bot = FileManagerBot()
    bot.run()

if __name__ == "__main__":
    main()
