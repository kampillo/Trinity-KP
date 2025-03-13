import os
import time
import random
import curses
import threading
import openai
from dotenv import load_dotenv

# Load environment variables (for OpenAI API key)
load_dotenv()

# Configure OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Constants
MATRIX_UPDATE_INTERVAL = 0.03  # 30ms per frame
MAIN_LOOP_INTERVAL = 0.01      # Pause to avoid excessive CPU usage
EXIT_COMMAND = "/q"            # Command to exit
AI_MODEL = "gpt-3.5-turbo"     # OpenAI model
MAX_TOKENS = 150               # Maximum tokens in response

class MatrixEffect:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        curses.start_color()
        curses.use_default_colors()
        
        # Color palette (can be customized)
        self.RAIN_COLOR = curses.COLOR_GREEN  # Color for Matrix "rain"
        self.TEXT_COLOR = curses.COLOR_WHITE  # Color for response text
        self.BG_COLOR = curses.COLOR_BLACK    # Background color
        
        # Initialize Matrix colors
        curses.init_pair(1, self.RAIN_COLOR, self.BG_COLOR)  # For Matrix rain
        curses.init_pair(2, self.TEXT_COLOR, self.BG_COLOR)  # For response text
        
        self.height, self.width = stdscr.getmaxyx()
        self.center_y = self.height // 2 - 5  # Center where response will be displayed
        self.response_text = ""
        self.response_chars = []  # Response characters
        self.revealed_positions = {}  # Mapping of positions where characters have been revealed
        self.columns = []
        self.is_active = False
        self.animation_done = False
        self.animation_start_time = 0
        self.MAX_ANIMATION_TIME = 15  # maximum seconds for animation
        self.init_columns()
        
    def init_columns(self):
        """Initialize columns for the matrix effect"""
        self.columns = []
        for i in range(self.width):
            speed = random.uniform(0.8, 2.0)
            self.columns.append({
                "pos": random.randint(-self.height, 0),  # Random initial position above the screen
                "speed": speed,
                "chars": [],
                "active": False,
                "response_char": None,  # Response character assigned to this column
                "response_pos": None,   # Position in x where to show the character (may be different from i)
                "revealed": False       # If character has been "fixed" in the center
            })
    
    def wrap_text(self, text, width):
        """Split text into lines that fit screen width"""
        words = text.split()
        lines = []
        current_line = []
        
        current_length = 0
        for word in words:
            # If the word is too long, split it
            if len(word) > width - 2:
                # If there's content in the current line, add it first
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = []
                    current_length = 0
                
                # Split the long word into chunks
                for i in range(0, len(word), width - 2):
                    fragment = word[i:i + width - 2]
                    if i + width - 2 < len(word):
                        fragment += '-'  # Add hyphen to indicate continuation
                    lines.append(fragment)
                
                continue
            
            # If the word fits in the current line
            if current_length + len(word) + (1 if current_length > 0 else 0) <= width:
                current_line.append(word)
                current_length += len(word) + (1 if current_length > 0 else 0)
            else:
                # If the line is full, start a new one
                lines.append(' '.join(current_line))
                current_line = [word]
                current_length = len(word)
        
        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))
            
        return lines
    
    def prepare_response(self, text):
        """Prepare the response for Matrix animation"""
        self.animation_done = False
        self.is_active = False
        self.animation_start_time = time.time()
        
        # Clear previous state
        self.response_text = text
        self.revealed_positions = {}
        
        # Prepare response format in center
        lines = self.wrap_text(text, self.width - 8)  # Wider margin
        self.response_chars = []
        
        # Limit number of lines for very long responses
        max_visible_lines = min(self.height - 8, 15)  # More conservative with line count
        if len(lines) > max_visible_lines:
            # If there are too many lines, show only what fits
            # and add a "..." indicator
            lines = lines[:max_visible_lines-1]
            lines.append("... (Response truncated)")
        
        # Create character list with their screen positions
        x_offset = 2  # Left margin
        y_offset = self.center_y - (len(lines) // 2)  # Center vertically
        
        # Ensure y_offset is positive
        y_offset = max(1, y_offset)
        
        for line_idx, line in enumerate(lines):
            line_y = y_offset + line_idx
            if line_y < 0 or line_y >= self.height - 3:
                continue  # Skip lines outside the screen
            
            # Center the line horizontally
            line_x_offset = x_offset + (self.width - 8 - len(line)) // 2
            
            for char_idx, char in enumerate(line):
                char_x = line_x_offset + char_idx
                if char_x < 0 or char_x >= self.width:
                    continue  # Skip characters outside the screen
                
                # Add this character to the list of characters to display
                if char != ' ':  # Ignore spaces, they will be displayed automatically
                    self.response_chars.append({
                        "char": char,
                        "x": char_x,
                        "y": line_y,
                        "revealed": False
                    })
        
        # Reset columns
        self.init_columns()
        
        # For long responses, limit the total number of characters to animate
        # to improve performance
        max_chars_to_animate = min(300, len(self.response_chars))
        
        if len(self.response_chars) > max_chars_to_animate:
            # Organize characters by lines to select a representative subset
            chars_by_line = {}
            for char in self.response_chars:
                y = char["y"]
                if y not in chars_by_line:
                    chars_by_line[y] = []
                chars_by_line[y].append(char)
            
            # Select some characters from each line
            selected_chars = []
            for y, chars in chars_by_line.items():
                # Distribute quota proportionally to number of lines
                quota_per_line = max(5, max_chars_to_animate // len(chars_by_line))
                # Take a sample of characters from this line, prioritizing uniform spacing
                if len(chars) <= quota_per_line:
                    selected_from_line = chars
                else:
                    # Take uniformly distributed characters
                    indices = [int(i * len(chars) / quota_per_line) for i in range(quota_per_line)]
                    selected_from_line = [chars[i] for i in indices]
                
                selected_chars.extend(selected_from_line)
                
                # If we already have enough characters, stop
                if len(selected_chars) >= max_chars_to_animate:
                    break
            
            # Mark non-selected characters as already revealed
            for char in self.response_chars:
                if char not in selected_chars:
                    char["revealed"] = True
                    
            # For very long responses, use only selected characters for animation
            animated_chars = selected_chars
        else:
            animated_chars = self.response_chars
        
        # Limit maximum active columns to improve performance
        max_active_columns = min(100, len(animated_chars))
        
        # Activate columns for characters selected for animation
        available_columns = list(range(self.width))
        random.shuffle(available_columns)
        
        for i, char in enumerate(animated_chars[:max_active_columns]):
            if i >= len(available_columns):
                break
                
            col_idx = available_columns[i]
            self.columns[col_idx]["active"] = True
            
            # Assign a response character to this column
            self.columns[col_idx]["response_char"] = char["char"]
            self.columns[col_idx]["response_pos"] = (char["x"], char["y"])
            
            # Adjust speed based on position and to improve visual rhythm
            # For characters lower on screen, slightly higher speed
            base_speed = random.uniform(0.8, 1.5)
            position_factor = 1.0 + (char["y"] / self.height)
            self.columns[col_idx]["speed"] = base_speed * position_factor
            
            # Generate random characters for rain - shorter chains
            chain_length = random.randint(3, 8)  # Shorter chains for better performance
            chars = []
            
            # First character in column is response character
            chars.append(self.columns[col_idx]["response_char"])
            
            # Rest are random characters
            for _ in range(chain_length - 1):
                chars.append(self.get_random_matrix_char())
            
            self.columns[col_idx]["chars"] = chars
        
        # Activate some additional columns for visual effect (without response characters)
        # but fewer for long responses
        extra_cols = min(self.width // 5, 20)  # Limit extra columns for better performance
        
        for i in range(min(extra_cols, len(available_columns) - max_active_columns)):
            if i + max_active_columns >= len(available_columns):
                break
                
            col_idx = available_columns[i + max_active_columns]
            self.columns[col_idx]["active"] = True
            
            # Just random characters, shorter chains
            chain_length = random.randint(3, 6)
            chars = []
            for _ in range(chain_length):
                chars.append(self.get_random_matrix_char())
            
            self.columns[col_idx]["chars"] = chars
        
        # Activate animation
        self.is_active = True
    
    def get_random_matrix_char(self):
        """Return a random Matrix-style character"""
        matrix_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;':\",./<>?"
        return random.choice(matrix_chars)
        
    def update(self):
        """Update and draw Matrix effect"""
        if not self.is_active and not self.animation_done:
            return
            
        # Check if animation has lasted too long
        current_time = time.time()
        if current_time - self.animation_start_time > self.MAX_ANIMATION_TIME:
            # Reveal all remaining characters
            for char_info in self.response_chars:
                char_info["revealed"] = True
            self.animation_done = True
            self.is_active = False
            self.draw_revealed_chars()
            return
            
        # Clear screen
        self.stdscr.clear()
        
        # If animation is done, just show final response
        if self.animation_done:
            self.draw_revealed_chars()
            return
        
        # For long responses, force reveal some characters per frame
        # to avoid animation getting stuck
        char_reveal_quota = 3  # Number of characters to forcibly reveal per frame
        chars_revealed_this_frame = 0
        
        # Calculate how many characters remain to be revealed
        unrevealed_chars = [c for c in self.response_chars if not c["revealed"]]
        total_unrevealed = len(unrevealed_chars)
        
        # If few characters remain unrevealed, increase completion force
        if 0 < total_unrevealed < 20:
            char_reveal_quota = 5
        
        # Update and draw active columns
        any_active = False
        
        # Limit number of active columns processed per frame to improve performance
        max_active_per_frame = 100
        active_columns = [i for i, col in enumerate(self.columns) if col["active"]]
        
        # For very long responses, process a subset in each frame
        if len(active_columns) > max_active_per_frame:
            # Ensure we process different columns in each frame
            random.shuffle(active_columns)
            active_columns = active_columns[:max_active_per_frame]
        
        for i in active_columns:
            col = self.columns[i]
            any_active = True
            
            # Update position
            col["pos"] += col["speed"]
            
            # Check if column has reached center and has a response character
            if col["response_char"] and not col["revealed"]:
                if col["pos"] >= col["response_pos"][1]:
                    # "Fix" character in its final position
                    col["revealed"] = True
                    
                    # Mark this character as revealed in response characters
                    for char_info in self.response_chars:
                        if (char_info["x"] == col["response_pos"][0] and 
                            char_info["y"] == col["response_pos"][1] and 
                            char_info["char"] == col["response_char"] and
                            not char_info["revealed"]):
                            char_info["revealed"] = True
                            chars_revealed_this_frame += 1
                            break
            
            # Draw falling characters - limit chain length for better performance
            max_chain_length = 10  # Reduce for better performance
            for j, char in enumerate(col["chars"][:max_chain_length]):
                # Current position of character
                y_pos = int(col["pos"]) - j
                
                # Only draw if inside screen and not in input area
                if 0 <= y_pos < self.height - 3:
                    try:
                        # Highlight first character (response character)
                        if j == 0 and col["response_char"]:
                            self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                        else:
                            self.stdscr.attron(curses.color_pair(1))
                        
                        # Draw character
                        self.stdscr.addch(y_pos, i, char)
                        
                        # Reset attributes
                        self.stdscr.attroff(curses.A_BOLD)
                        self.stdscr.attroff(curses.color_pair(1))
                        self.stdscr.attroff(curses.color_pair(2))
                    except curses.error:
                        pass
            
            # If column has been revealed, deactivate it when it leaves screen
            if col["revealed"] and col["pos"] > self.height:
                col["active"] = False
            # If column without response character leaves screen, reset it
            elif not col["response_char"] and col["pos"] > self.height:
                col["pos"] = random.randint(-self.height // 2, 0)
        
        # Force reveal some characters if necessary
        # to avoid animation getting stuck
        if chars_revealed_this_frame < char_reveal_quota and unrevealed_chars:
            # Select some random characters to reveal
            chars_to_force = min(char_reveal_quota - chars_revealed_this_frame, len(unrevealed_chars))
            for _ in range(chars_to_force):
                if unrevealed_chars:
                    char_info = random.choice(unrevealed_chars)
                    char_info["revealed"] = True
                    unrevealed_chars.remove(char_info)
        
        # Draw already revealed characters
        self.draw_revealed_chars()
        
        # Check if all characters have been revealed
        all_revealed = len(unrevealed_chars) == 0 and len(self.response_chars) > 0
        
        # If no active columns or all characters revealed
        # or too much time has passed, finish animation
        if not any_active or all_revealed:
            self.animation_done = True
            self.is_active = False
    
    def draw_revealed_chars(self):
        """Draw response characters that have already been revealed"""
        # First group by line to optimize performance
        chars_by_line = {}
        for char_info in self.response_chars:
            if char_info["revealed"]:
                y = char_info["y"]
                if y not in chars_by_line:
                    chars_by_line[y] = []
                chars_by_line[y].append(char_info)
        
        # Sort each line by x position
        for y in chars_by_line:
            chars_by_line[y].sort(key=lambda c: c["x"])
            
        # Draw line by line - this is more efficient
        for y, chars in chars_by_line.items():
            for char_info in chars:
                try:
                    self.stdscr.attron(curses.color_pair(2) | curses.A_BOLD)
                    self.stdscr.addch(char_info["y"], char_info["x"], char_info["char"])
                    self.stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
                except curses.error:
                    pass
                    
        # Draw a border around text area to improve readability
        # but only if there are revealed characters
        if chars_by_line:
            try:
                min_y = min(chars_by_line.keys())
                max_y = max(chars_by_line.keys())
                
                min_x = min([min([c["x"] for c in line]) for line in chars_by_line.values()])
                max_x = max([max([c["x"] for c in line]) for line in chars_by_line.values()])
                
                # Add margin
                min_y = max(0, min_y - 1)
                max_y = min(self.height - 4, max_y + 1)
                min_x = max(0, min_x - 2)
                max_x = min(self.width - 1, max_x + 2)
                
                # Draw horizontal borders
                self.stdscr.attron(curses.color_pair(1))
                for x in range(min_x, max_x + 1):
                    try:
                        self.stdscr.addch(min_y, x, curses.ACS_HLINE)
                        self.stdscr.addch(max_y, x, curses.ACS_HLINE)
                    except curses.error:
                        pass
                
                # Draw vertical borders
                for y in range(min_y + 1, max_y):
                    try:
                        self.stdscr.addch(y, min_x, curses.ACS_VLINE)
                        self.stdscr.addch(y, max_x, curses.ACS_VLINE)
                    except curses.error:
                        pass
                
                # Draw corners
                try:
                    self.stdscr.addch(min_y, min_x, curses.ACS_ULCORNER)
                    self.stdscr.addch(min_y, max_x, curses.ACS_URCORNER)
                    self.stdscr.addch(max_y, min_x, curses.ACS_LLCORNER)
                    self.stdscr.addch(max_y, max_x, curses.ACS_LRCORNER)
                except curses.error:
                    pass
                
                self.stdscr.attroff(curses.color_pair(1))
            except (ValueError, curses.error):
                # If there's any error drawing the border, just ignore it
                pass

class ChatApp:
    def __init__(self):
        self.messages = [{"role": "system", "content": "You are Trinity from The Matrix. Respond as if you are this character - cool, direct, and technically knowledgeable. You have a slight edge to your personality, but you're helpful. If asked about who you are, mention you're Trinity from The Matrix. Keep your responses concise and efficient, like Trinity would."}]
        self.user_input = ""
        self.history = []  # History of sent messages
        self.history_index = 0  # Current index in history
        
    def add_message(self, role, content):
        """Add a message to conversation history"""
        self.messages.append({"role": role, "content": content})
        
        # If it's a user message, add it to command history
        if role == "user" and content.strip() and content != EXIT_COMMAND:
            self.history.append(content)
            self.history_index = len(self.history)
        
    def get_response(self):
        """Get response from OpenAI API"""
        try:
            response = openai.chat.completions.create(
                model=AI_MODEL,
                messages=self.messages,
                max_tokens=MAX_TOKENS
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error connecting to OpenAI: {str(e)}"
    
    def get_previous_command(self):
        """Get previous command from history"""
        if self.history and self.history_index > 0:
            self.history_index -= 1
            return self.history[self.history_index]
        return self.user_input
    
    def get_next_command(self):
        """Get next command from history"""
        if self.history and self.history_index < len(self.history) - 1:
            self.history_index += 1
            return self.history[self.history_index]
        elif self.history_index == len(self.history) - 1:
            self.history_index = len(self.history)
            return ""
        return self.user_input
    
    def save_conversation(self, filename="matrix_chat_history.txt"):
        """Save current conversation to text file"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for msg in self.messages[1:]:  # Skip system message
                    role = "User" if msg["role"] == "user" else "Assistant"
                    f.write(f"[{role}]:\n{msg['content']}\n\n")
            return f"Conversation saved to {filename}"
        except Exception as e:
            return f"Error saving conversation: {str(e)}"


def display_help(win, height, width):
    """Show help window with available commands"""
    help_height = 16
    help_width = 60
    help_win = curses.newwin(help_height, help_width, height//2 - help_height//2, width//2 - help_width//2)
    help_win.box()
    
    # Title
    help_win.attron(curses.A_BOLD)
    help_win.addstr(1, help_width//2 - 10, "MATRIX CHAT HELP")
    help_win.attroff(curses.A_BOLD)
    
    # Commands section
    help_win.addstr(3, 2, "Available commands:")
    commands = [
        (f"{EXIT_COMMAND}", "Exit program"),
        ("/help", "Show this help"),
        ("/clear", "Clear conversation history"),
        ("/save", "Save conversation to file"),
        ("/model [name]", "Change model (gpt-3.5-turbo, gpt-4, etc.)"),
        ("/system", "Show system information"),
        ("/color [name]", "Change color (green, red, blue, etc.)")
    ]
    
    for i, (cmd, desc) in enumerate(commands):
        help_win.addstr(4 + i, 4, cmd)
        help_win.addstr(4 + i, 20, desc)
    
    # Navigation keys section
    help_win.addstr(12, 2, "Navigation keys:")
    help_win.addstr(13, 4, "Up/Down arrows")
    help_win.addstr(13, 25, "Navigate through history")
    
    # Footer
    help_win.addstr(help_height - 2, 4, "Press any key to continue...")
    
    help_win.refresh()
    help_win.getch()


def main(stdscr):
    # Initial curses setup
    curses.curs_set(0)  # Hide cursor
    stdscr.nodelay(True)  # Non-blocking mode for getch()
    stdscr.clear()
    
    # Create instances
    matrix = MatrixEffect(stdscr)
    chat = ChatApp()
    
    # Calculate dimensions
    height, width = stdscr.getmaxyx()
    
    # Text input area (3 lines high, at bottom)
    input_win = curses.newwin(3, width, height - 3, 0)
    input_win.box()
    input_prefix = "Type your message: "
    input_win.addstr(1, 2, input_prefix)
    input_win.refresh()
    
    # Control variables
    running = True
    waiting_response = False
    status_message = ""
    status_time = 0
    
    # Function to get OpenAI response in separate thread
    def get_ai_response(user_text):
        nonlocal waiting_response, status_message, status_time
        try:
            # Show "Connecting..." message during API query
            input_win.clear()
            input_win.box()
            input_win.addstr(1, 2, "Connecting to OpenAI...")
            input_win.refresh()
            
            chat.add_message("user", user_text)
            
            # For longer questions, adjust max tokens
            tokens_estimate = len(user_text) // 4  # rough estimate
            adjusted_max_tokens = min(300, MAX_TOKENS + tokens_estimate)
            
            # Show "Processing response..." message
            input_win.clear()
            input_win.box()
            input_win.addstr(1, 2, "Processing response...")
            input_win.refresh()
            
            # Try to get response with retry if connection error
            max_retries = 2
            retry_count = 0
            
            while retry_count <= max_retries:
                try:
                    # Get response with adjusted max_tokens and lower temperature
                    response = openai.chat.completions.create(
                        model=AI_MODEL,
                        messages=chat.messages,
                        max_tokens=adjusted_max_tokens,
                        temperature=0.7
                    ).choices[0].message.content
                    break  # If successful, exit loop
                except Exception as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        raise  # Re-raise exception if we've exhausted attempts
                    
                    # Report retry
                    input_win.clear()
                    input_win.box()
                    input_win.addstr(1, 2, f"Connection error. Retrying ({retry_count}/{max_retries})...")
                    input_win.refresh()
                    time.sleep(2)  # Wait before retrying
            
            # Shorten extremely long responses before processing
            if len(response) > 1000:
                # Find a good point to cut (ideally at end of sentence)
                cutoff_point = 1000
                while cutoff_point > 800 and response[cutoff_point] not in ['.', '!', '?']:
                    cutoff_point -= 1
                
                if cutoff_point > 800:
                    response = response[:cutoff_point+1] + "\n\n... (Response truncated)"
                else:
                    response = response[:1000] + "\n\n... (Response truncated)"
            
            # Show "Generating animation..." message
            input_win.clear()
            input_win.box()
            input_win.addstr(1, 2, "Generating Matrix animation...")
            input_win.refresh()
            
            chat.add_message("assistant", response)
            matrix.prepare_response(response)
        except Exception as e:
            status_message = f"Error: {str(e)}"
            status_time = time.time()
        finally:
            waiting_response = False
    
    # Show initial message
    welcome_message = """Welcome to the Matrix. I'm Trinity.

Follow the white rabbit. Or just type your questions below.

Useful commands:
- /help : Show full help
- /q : Exit program

Type your message and press Enter to start.
"""
    matrix.prepare_response(welcome_message)
    
    # Main loop
    last_update_time = time.time()
    
    while running:
        # Check if it's time to update screen
        current_time = time.time()
        if current_time - last_update_time >= MATRIX_UPDATE_INTERVAL:
            # Update Matrix effect
            matrix.update()
            stdscr.refresh()
            last_update_time = current_time
        
        # Process user input (non-blocking)
        try:
            key = stdscr.getch()
        except curses.error:
            key = -1
        
        # Clear status message if enough time has passed
        if status_message and current_time - status_time > 3:
            status_message = ""
        
        # Process keys
        if key == curses.KEY_ENTER or key == 10 or key == 13:  # Enter
            if chat.user_input.strip() and not waiting_response:
                user_text = chat.user_input.strip()
                chat.user_input = ""
                
                # Check if special command
                if user_text == EXIT_COMMAND:
                    # Show goodbye message before exit
                    input_win.clear()
                    input_win.box()
                    input_win.addstr(1, 2, "Goodbye! Exiting...")
                    input_win.refresh()
                    time.sleep(1)
                    running = False
                    continue
                elif user_text == "/help":
                    display_help(input_win, height, width)
                elif user_text == "/clear":
                    # Clear conversation history
                    chat.messages = [{"role": "system", "content": "You are Trinity from The Matrix. Respond as if you are this character - cool, direct, and technically knowledgeable. You have a slight edge to your personality, but you're helpful. If asked about who you are, mention you're Trinity from The Matrix. Keep your responses concise and efficient, like Trinity would."}]
                    matrix.prepare_response("Conversation history cleared.")
                elif user_text == "/save":
                    result = chat.save_conversation()
                    matrix.prepare_response(result)
                elif user_text.startswith("/model "):
                    # Change OpenAI model
                    model_name = user_text[7:].strip()
                    if model_name in ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]:
                        global AI_MODEL
                        AI_MODEL = model_name
                        matrix.prepare_response(f"Model changed to {AI_MODEL}.")
                    else:
                        matrix.prepare_response(f"Model not recognized. Available models: gpt-3.5-turbo, gpt-4, gpt-4-turbo")
                elif user_text == "/system":
                    # Show system information
                    system_info = f"""
Terminal: {width}x{height} characters
Current model: {AI_MODEL}
Maximum tokens: {MAX_TOKENS}
History: {len(chat.messages)-1} messages
API Key: {'Configured' if openai.api_key else 'Not configured'}
"""
                    matrix.prepare_response(system_info)
                elif user_text.startswith("/color "):
                    color_name = user_text[7:].strip().lower()
                    color_map = {
                        "green": curses.COLOR_GREEN,
                        "red": curses.COLOR_RED,
                        "blue": curses.COLOR_BLUE,
                        "cyan": curses.COLOR_CYAN,
                        "magenta": curses.COLOR_MAGENTA,
                        "yellow": curses.COLOR_YELLOW,
                        "white": curses.COLOR_WHITE
                    }
                    
                    if color_name in color_map:
                        matrix.RAIN_COLOR = color_map[color_name]
                        curses.init_pair(1, matrix.RAIN_COLOR, matrix.BG_COLOR)
                        matrix.prepare_response(f"Matrix color changed to {color_name}.")
                    else:
                        matrix.prepare_response(f"Color not recognized. Available colors: {', '.join(color_map.keys())}")
                else:
                    # Show "Waiting for response..." message
                    input_win.clear()
                    input_win.box()
                    input_win.addstr(1, 2, "Waiting for response...")
                    input_win.refresh()
                    
                    # Start thread to get response
                    waiting_response = True
                    threading.Thread(target=get_ai_response, args=(user_text,), daemon=True).start()
        elif key == curses.KEY_BACKSPACE or key == 127 or key == 8:  # Backspace (different codes)
            if chat.user_input:
                chat.user_input = chat.user_input[:-1]
        elif key == curses.KEY_UP:  # Up arrow to navigate history
            chat.user_input = chat.get_previous_command()
        elif key == curses.KEY_DOWN:  # Down arrow to navigate history
            chat.user_input = chat.get_next_command()
        elif key != -1 and not waiting_response and 32 <= key <= 126:  # Printable characters
            if len(chat.user_input) < width - len(input_prefix) - 5:  # Limit length
                chat.user_input += chr(key)
        
        # Update input window if not waiting for response
        if not waiting_response:
            input_win.clear()
            input_win.box()
            
            # Show status message if exists
            if status_message:
                input_win.addstr(0, 5, status_message[:width-10], curses.A_ITALIC)
                
            # Show user input
            input_win.addstr(1, 2, f"{input_prefix}{chat.user_input}")
            input_win.refresh()
        
        # Small pause to avoid excessive CPU usage
        time.sleep(MAIN_LOOP_INTERVAL)


if __name__ == "__main__":
    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING! OpenAI API key not found.")
        print("Configure the OPENAI_API_KEY environment variable or create a .env file")
        print("Example: OPENAI_API_KEY=sk-...")
        exit(1)
    
    # Start application
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        print("Program terminated by user.")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
