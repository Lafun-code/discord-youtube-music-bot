# Discord YouTube Music Bot

A feature-rich Discord bot that can play music from YouTube, manage a queue, and provide a user-friendly interface.

## Features
- Play, pause, skip, and stop songs
- Queue management for continuous playback
- Support for YouTube playlists
- Adjust volume levels
- Admin-only message cleanup commands

## Requirements
- Python 3.8 or higher
- Libraries:
  - `discord.py`
  - `yt_dlp`
- FFmpeg (for audio processing)

## Installation
1. Clone the repository:
    ```bash
    git clone https://github.com/Lafun-code/discord-youtube-music-bot
    cd discord-youtube-music-bot
    ```

2. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

3. Edit `bot.py`:
    - Replace `YOUR_DISCORD_BOT_TOKEN` in the following line:
      ```python
      bot.run('YOUR_DISCORD_BOT_TOKEN')
      ```

4. Run the bot:
    ```bash
    python bot.py
    ```

## Commands
- `!play [song name or URL]`: Play a song or add it to the queue (shortcut: `!p`).
- `!pause`: Pause the currently playing song.
- `!resume`: Resume the paused song.
- `!skip`: Skip to the next song in the queue.
- `!stop`: Stop the music and disconnect from the voice channel.
- `!playlist [YouTube playlist URL]`: Add all songs from a YouTube playlist to the queue.
- `!volume [0-100]`: Adjust the playback volume.
- `!nowplaying`: Show the currently playing song.
- `!clearqueue`: Clear the current song queue.
- `!sil [number]`: Delete the specified number of messages (admin-only).
- `!commands`: Show a list of all commands.

## Contribution
Feel free to contribute to this project by opening an issue or submitting a pull request.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
