import customtkinter as ctk
import discord
import asyncio
import threading
import json
import os
import queue
import traceback
from datetime import datetime
from tkinter import messagebox

HISTORY_FILE = 'messages.json'


class BotClient(discord.Client):
    def __init__(self, gui_queue, loop_container, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gui_queue = gui_queue
        self.loop_container = loop_container

    async def on_ready(self):
        try:
            self.loop_container['loop'] = asyncio.get_event_loop()
            self.loop_container['client'] = self
            self.gui_queue.put({'type': 'status', 'status': 'online'})
            print(f'Logged in as {self.user} (ID: {self.user.id})')
        except Exception:
            traceback.print_exc()

    async def on_message(self, message: discord.Message):
        # Only handle direct messages (DMs)
        try:
            if message.author == self.user:
                return
            if message.guild is None:
                timestamp = datetime.utcnow().isoformat()
                data = {
                    'type': 'received',
                    'user_id': str(message.author.id),
                    'username': str(message.author),
                    'content': message.content,
                    'timestamp': timestamp,
                }
                self.gui_queue.put({'type': 'message', 'payload': data})
        except Exception:
            traceback.print_exc()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode('Dark')
        ctk.set_default_color_theme('dark-blue')
        self.title('Discord DM Dashboard')
        self.geometry('1000x700')
        self.minsize(800, 500)

        # Shared structures
        self.gui_queue = queue.Queue()
        self.loop_container = {}
        self.history = {}
        self.current_user = None

        # Load history
        self.load_history()

        # Layout: left list, center chat, right controls
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left: conversations
        self.left_frame = ctk.CTkFrame(self)
        self.left_frame.grid(row=0, column=0, sticky='nswe', padx=8, pady=8)
        self.left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(self.left_frame, text='Conversations').grid(row=0, column=0, padx=8, pady=4)
        self.conv_listbox = ctk.CTkScrollableFrame(self.left_frame, width=200, height=400)
        self.conv_listbox.grid(row=1, column=0, sticky='nswe', padx=8, pady=4)

        self.refresh_conversations()

        # Center: main chat area
        self.center_frame = ctk.CTkFrame(self)
        self.center_frame.grid(row=0, column=1, sticky='nswe', padx=8, pady=8)
        self.center_frame.grid_rowconfigure(1, weight=1)
        self.center_frame.grid_columnconfigure(0, weight=1)

        # Top: token and status
        top_bar = ctk.CTkFrame(self.center_frame)
        top_bar.grid(row=0, column=0, sticky='we', pady=(0, 4))
        top_bar.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(top_bar, text='Bot Token:').grid(row=0, column=0, padx=6, pady=6)
        self.token_entry = ctk.CTkEntry(top_bar, show='*')
        self.token_entry.grid(row=0, column=1, padx=6, pady=6)
        self.connect_btn = ctk.CTkButton(top_bar, text='Connect Bot', command=self.connect_bot)
        self.connect_btn.grid(row=0, column=2, padx=6, pady=6)
        self.status_label = ctk.CTkLabel(top_bar, text='Status: Offline')
        self.status_label.grid(row=0, column=3, padx=6, pady=6, sticky='e')

        # Message board (ScrolledText)
        self.chat_text = ctk.CTkTextbox(self.center_frame, wrap='word')
        self.chat_text.grid(row=1, column=0, sticky='nswe', padx=4, pady=4)
        self.chat_text.configure(state='disabled')

        # Bottom: DM controls
        bottom = ctk.CTkFrame(self.center_frame)
        bottom.grid(row=2, column=0, sticky='we', pady=(4, 0))
        bottom.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(bottom, text='User ID:').grid(row=0, column=0, padx=6, pady=6)
        self.user_entry = ctk.CTkEntry(bottom)
        self.user_entry.grid(row=0, column=1, padx=6, pady=6, sticky='we')
        self.load_btn = ctk.CTkButton(bottom, text='Load', command=self.load_selected_conversation)
        self.load_btn.grid(row=0, column=2, padx=6, pady=6)

        self.msg_entry = ctk.CTkTextbox(bottom, height=80)
        self.msg_entry.grid(row=1, column=0, columnspan=3, padx=6, pady=6, sticky='we')
        self.send_btn = ctk.CTkButton(bottom, text='Send DM', command=self.send_dm)
        self.send_btn.grid(row=2, column=2, padx=6, pady=6, sticky='e')

        # Enter to send, Shift+Enter for newline in message box
        try:
            self.msg_entry.bind('<Shift-Return>', lambda e: self.msg_entry.insert('insert', '\n'))
            self.msg_entry.bind('<Return>', self.on_enter)
        except Exception:
            pass

        # Right: actions
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=2, sticky='nswe', padx=8, pady=8)
        self.right_frame.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(self.right_frame, text='Actions').grid(row=0, column=0, padx=8, pady=4)
        self.copy_btn = ctk.CTkButton(self.right_frame, text='Copy Selection', command=self.copy_selection)
        self.copy_btn.grid(row=1, column=0, padx=8, pady=4, sticky='we')
        self.clear_btn = ctk.CTkButton(self.right_frame, text='Clear Chat', fg_color='red', command=self.clear_chat)
        self.clear_btn.grid(row=2, column=0, padx=8, pady=4, sticky='we')

        ctk.CTkLabel(self.right_frame, text='Search Messages').grid(row=3, column=0, padx=8, pady=(12, 4))
        self.search_entry = ctk.CTkEntry(self.right_frame)
        self.search_entry.grid(row=4, column=0, padx=8, pady=4, sticky='we')
        self.search_btn = ctk.CTkButton(self.right_frame, text='Search', command=self.search_messages)
        self.search_btn.grid(row=5, column=0, padx=8, pady=4, sticky='we')

        # Periodic GUI poll
        self.after(200, self.process_queue)

        # Disable send until bot online
        self.update_send_buttons(False)

    def refresh_conversations(self):
        # Clear current listbox content
        for widget in self.conv_listbox.winfo_children():
            widget.destroy()
        # Show saved conversations
        for uid, messages in sorted(self.history.items(), key=lambda x: x[0], reverse=True):
            username = messages[-1].get('username', uid) if messages else uid
            btn = ctk.CTkButton(self.conv_listbox, text=f'{username}\n{uid}', anchor='w', command=lambda u=uid: self.select_conversation(u))
            btn.pack(fill='x', padx=4, pady=2)

    def select_conversation(self, user_id):
        self.user_entry.delete(0, 'end')
        self.user_entry.insert(0, user_id)
        self.load_selected_conversation()

    def load_selected_conversation(self):
        uid = self.user_entry.get().strip()
        if not uid:
            messagebox.showinfo('Info', 'Please enter a user ID to load.')
            return
        self.current_user = uid
        self.display_conversation(uid)

    def display_conversation(self, user_id, filtered=None):
        messages = self.history.get(user_id, [])
        if filtered is not None:
            messages = filtered
        self.chat_text.configure(state='normal')
        self.chat_text.delete('1.0', 'end')
        for m in messages:
            ts = m.get('timestamp')
            try:
                dt = datetime.fromisoformat(ts)
                ttext = dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                ttext = ts
            author = m.get('author', m.get('username', 'Unknown'))
            direction = m.get('direction', m.get('type', 'received'))
            if direction == 'sent' or m.get('type') == 'sent':
                label = f'[{ttext}] Me:\n{m.get("content")}\n\n'
            else:
                label = f'[{ttext}] {author}:\n{m.get("content")}\n\n'
            self.chat_text.insert('end', label)
        self.chat_text.configure(state='disabled')
        self.chat_text.yview_moveto(1.0)

    def process_queue(self):
        while not self.gui_queue.empty():
            item = self.gui_queue.get()
            if item.get('type') == 'status':
                st = item.get('status')
                if st == 'online':
                    self.status_label.configure(text='Status: Online')
                    self.update_send_buttons(True)
                elif st == 'connecting':
                    self.status_label.configure(text='Status: Connecting')
                else:
                    self.status_label.configure(text=f'Status: {st}')
            elif item.get('type') == 'message':
                payload = item.get('payload')
                uid = payload.get('user_id')
                entry = {
                    'timestamp': payload.get('timestamp'),
                    'username': payload.get('username'),
                    'content': payload.get('content'),
                    'type': 'received',
                    'author': payload.get('username'),
                }
                self.history.setdefault(uid, []).append(entry)
                self.save_history()
                # If current open conversation, append to board
                if self.current_user == uid:
                    self.append_message_to_board(entry)
                self.refresh_conversations()
        self.after(200, self.process_queue)

    def append_message_to_board(self, entry):
        self.chat_text.configure(state='normal')
        try:
            dt = datetime.fromisoformat(entry.get('timestamp'))
            ttext = dt.strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            ttext = entry.get('timestamp')
        author = entry.get('author', entry.get('username', 'User'))
        if entry.get('type') == 'sent' or entry.get('direction') == 'sent':
            text = f'[{ttext}] Me:\n{entry.get("content")}\n\n'
        else:
            text = f'[{ttext}] {author}:\n{entry.get("content")}\n\n'
        self.chat_text.insert('end', text)
        self.chat_text.configure(state='disabled')
        self.chat_text.yview_moveto(1.0)

    def update_send_buttons(self, enabled: bool):
        state = 'normal' if enabled else 'disabled'
        self.send_btn.configure(state=state)
        self.load_btn.configure(state=state)

    def on_enter(self, event=None):
        """Handle Enter pressed in the message box: send once and prevent newline."""
        try:
            # If send is disabled, do nothing
            try:
                if self.send_btn.cget('state') == 'disabled':
                    return 'break'
            except Exception:
                pass
            # Trigger send
            self.send_dm()
        except Exception:
            try:
                traceback.print_exc()
            except Exception:
                pass
        return 'break'

    def connect_bot(self):
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showwarning('Token', 'Please enter your bot token in the Bot Token field.')
            return
        # Indicate connecting
        self.gui_queue.put({'type': 'status', 'status': 'connecting'})
        # Start background thread to run discord client
        thread = threading.Thread(target=self._run_bot_thread, args=(token,), daemon=True)
        thread.start()
        self.connect_btn.configure(state='disabled')

    def _run_bot_thread(self, token):
        try:
            intents = discord.Intents.default()
            intents.message_content = True
            intents.dm_messages = True
            client = BotClient(self.gui_queue, self.loop_container, intents=intents)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(client.start(token))
            finally:
                loop.run_until_complete(client.close())
                loop.stop()
        except Exception as e:
            tb = traceback.format_exc()
            print(tb)
            self.gui_queue.put({'type': 'status', 'status': f'error: {e}'})
            messagebox.showerror('Connection Error', f'Failed to connect bot:\n{e}')
            self.connect_btn.configure(state='normal')

    def send_dm(self):
        uid = self.user_entry.get().strip()
        content = self.msg_entry.get('1.0', 'end').strip()
        if not uid or not content:
            messagebox.showwarning('Missing', 'Please provide a User ID and message content.')
            return
        if 'loop' not in self.loop_container or 'client' not in self.loop_container:
            messagebox.showwarning('Bot', 'Bot is not connected.')
            return
        try:
            user_id_int = int(uid)
        except Exception:
            messagebox.showerror('Invalid ID', 'User ID must be an integer.')
            return

        async def _send_and_record():
            try:
                client = self.loop_container.get('client')
                user = await client.fetch_user(user_id_int)
                await user.send(content)
                timestamp = datetime.utcnow().isoformat()
                entry = {
                    'timestamp': timestamp,
                    'username': str(user),
                    'content': content,
                    'type': 'sent',
                    'author': 'Me',
                }
                # Put into gui queue so it gets saved and displayed on main thread
                self.gui_queue.put({'type': 'sent_message', 'user_id': str(user.id), 'entry': entry})
            except Exception as e:
                tb = traceback.format_exc()
                print(tb)
                self.gui_queue.put({'type': 'status', 'status': f'error: {e}'})
                messagebox.showerror('Send Failed', f'Failed to send DM:\n{e}')

        # Run coroutine in bot loop
        coro = _send_and_record()
        try:
            asyncio.run_coroutine_threadsafe(coro, self.loop_container['loop'])
            # Clear message box after sending
            self.msg_entry.delete('1.0', 'end')
        except Exception as e:
            messagebox.showerror('Error', f'Failed scheduling send task: {e}')

    def copy_selection(self):
        try:
            selected = self.chat_text.get('sel.first', 'sel.last')
            self.clipboard_clear()
            self.clipboard_append(selected)
            messagebox.showinfo('Copied', 'Selection copied to clipboard.')
        except Exception:
            messagebox.showinfo('Copy', 'No selection to copy.')

    def clear_chat(self):
        if not self.current_user:
            messagebox.showinfo('Info', 'No conversation selected.')
            return
        if messagebox.askyesno('Confirm', 'Clear conversation and delete history for this user?'):
            self.history.pop(self.current_user, None)
            self.save_history()
            self.display_conversation(self.current_user)
            self.refresh_conversations()

    def search_messages(self):
        term = self.search_entry.get().strip().lower()
        if not self.current_user:
            messagebox.showinfo('Info', 'Load a conversation first to search.')
            return
        if not term:
            self.display_conversation(self.current_user)
            return
        messages = self.history.get(self.current_user, [])
        filtered = [m for m in messages if term in m.get('content', '').lower() or term in m.get('username', '').lower()]
        self.display_conversation(self.current_user, filtered=filtered)

    def save_history(self):
        try:
            with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception:
            traceback.print_exc()

    def load_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception:
                traceback.print_exc()
                self.history = {}
        else:
            self.history = {}


def main():
    app = App()

    # Small hook: when GUI processes a sent_message event, integrate it
    original_process_queue = app.process_queue

    def patched_process_queue():
        while not app.gui_queue.empty():
            item = app.gui_queue.get()
            if item.get('type') == 'sent_message':
                uid = item.get('user_id')
                entry = item.get('entry')
                app.history.setdefault(uid, []).append(entry)
                app.save_history()
                if app.current_user == uid:
                    app.append_message_to_board(entry)
                app.refresh_conversations()
            else:
                # Put it back and let normal processor handle it
                app.gui_queue.put(item)
                break
        # Call normal processor for other items
        original_process_queue()

    app.process_queue = patched_process_queue
    app.after(200, app.process_queue)

    app.mainloop()


if __name__ == '__main__':
    main()
