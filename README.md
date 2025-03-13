# Trinity-KP

A terminal-based chat application featuring Trinity from The Matrix with stunning digital rain animation effects. Chat with Trinity while watching AI responses materialize through Matrix-style visual effects.

![KP-Matrix-Chat Demo](demo_screenshot.png)
*(Add a screenshot or GIF of your application here)*

## Features

- 🔄 Matrix-style digital rain animation for displaying AI responses
- 👩‍💻 Chat with Trinity from The Matrix
- 🤖 Integration with OpenAI's GPT models (gpt-3.5-turbo, gpt-4, etc.)
- 🎨 Customizable Matrix rain colors
- 📋 Command history navigation
- 💾 Save conversation to file
- ⚙️ Model switching and system information

## Requirements

- Python 3.6+
- OpenAI API key
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/trinity-kp.git
   cd trinity-kp
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file in the project directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

Run the application:
```
python trinity-kp.py
```

### Commands

- `/help` - Show help information
- `/q` - Exit the application
- `/clear` - Clear conversation history
- `/save` - Save conversation to file
- `/model [name]` - Change the GPT model (e.g., `/model gpt-4`)
- `/system` - Show system information
- `/color [name]` - Change Matrix rain color (green, red, blue, cyan, magenta, yellow, white)

### Navigation

- **Up/Down Arrow Keys** - Navigate through command history

## How It Works

This application combines the classic Matrix "digital rain" visual effect with OpenAI's GPT models to create an engaging chat interface in the terminal. When you send a message to Trinity, her response appears through an authentic Matrix-style animation where characters "rain" down the screen before settling into place to form the response text.

The AI is configured to respond as Trinity from The Matrix, maintaining her cool, direct personality and technical knowledge, creating an immersive experience for fans of the movie.

The project uses:
- `curses` for terminal manipulation
- `threading` for non-blocking API calls
- `openai` for interaction with GPT models
- `python-dotenv` for environment variable management

## Project Structure

- `trinity-kp.py` - Main application file
- `.env` - Environment variables file (not tracked in git)
- `requirements.txt` - Required Python packages
- `README.md` - Project documentation

## Limitations

- Terminal size affects the display of long responses
- Maximum animation time is set to 15 seconds for performance
- API rate limits apply based on your OpenAI account

## Future Improvements

- Add streaming responses
- Implement local model support
- Add conversation context management
- Support for images and other media types
- Custom system prompts

## License

[MIT License](LICENSE)

## Author

Created by Juan Campillo (Kampiyo)

## Acknowledgments

- Inspired by "The Matrix" film series
- Built using OpenAI's API
