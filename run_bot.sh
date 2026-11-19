
#!/data/data/com.termux/files/usr/bin/bash

cd "$HOME/modern_discord_ai"
source venv/bin/activate

while true
do
    echo "Menjalankan Discord AI Bot..."
    python bot.py

    echo "Bot berhenti atau mengalami error."
    echo "Mencoba menjalankan ulang dalam 10 detik..."
    sleep 10
done
